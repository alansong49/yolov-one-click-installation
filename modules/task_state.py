"""部署任务断点状态管理。

应用场景：一键部署（含权重下载）过程中程序被误关闭/系统重启后，
下次启动可检测到未完成任务，从断点继续或彻底清理。

设计要点：
- JSON 状态文件持久化，写入采用「临时文件 + os.replace 原子替换」，
  避免写入中途崩溃留下半个损坏 JSON。
- 状态文件优先放程序运行目录（exe 同目录），不可写时自动落到
  %APPDATA%\\YOLO_AutoInstaller\\resume_state.json（与模型缓存兜底策略一致）。
- 下载进度落盘做节流（百分比变化 >=1% 且距上次 >=1.5 秒），避免刷盘。
- 已完成文件记录 SHA256 + 大小，恢复时校验，损坏文件自动撤销对应
  步骤的完成标记，触发重新下载。
"""

import hashlib
import json
import os
import time

from .platform_utils import get_runtime_dir

STATE_VERSION = 1
STATE_FILENAME = 'resume_state.json'


def sha256_of(path, chunk_size=1 << 20):
    """流式计算文件 SHA256，大文件只占常量内存。"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class TaskStateManager:
    """单个部署任务的断点状态读写。"""

    def __init__(self):
        self.primary_path = os.path.join(get_runtime_dir(), STATE_FILENAME)
        # 兜底路径：Windows 用 %APPDATA%，Linux/macOS 用 XDG 数据目录 ~/.local/share
        appdata = os.environ.get('APPDATA')
        if not appdata:
            xdg = os.environ.get('XDG_DATA_HOME')
            if xdg:
                appdata = xdg
            else:
                appdata = os.path.join(os.path.expanduser('~'), '.local', 'share')
        self.fallback_path = os.path.join(
            appdata, 'YOLO_AutoInstaller', STATE_FILENAME)
        self.path = self.primary_path
        self.state = None
        self._last_dl_save = 0.0
        self._last_dl_pct = -1

    # ---------- 基础读写 ----------

    def _save(self):
        if self.state is None:
            return False
        self.state['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        data = json.dumps(self.state, ensure_ascii=False, indent=2)
        for p in (self.primary_path, self.fallback_path):
            try:
                parent = os.path.dirname(p)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                tmp = p + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.write(data)
                os.replace(tmp, p)
                self.path = p
                return True
            except Exception:
                continue
        return False

    def load(self):
        """读取状态文件（主路径优先，兜底路径其次）。无效/损坏返回 None。"""
        for p in (self.primary_path, self.fallback_path):
            if not os.path.exists(p):
                continue
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    st = json.load(f)
                if isinstance(st, dict) and st.get('task_type') == 'deploy':
                    self.path = p
                    self.state = st
                    return st
            except Exception:
                continue
        return None

    def has_pending(self):
        st = self.state or self.load()
        return bool(st) and st.get('status') == 'in_progress'

    def clear(self):
        """任务完成/放弃后删除状态文件（主路径和兜底路径都清）。"""
        self.state = None
        for p in (self.primary_path, self.fallback_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    # ---------- 任务生命周期 ----------

    def begin_task(self, *, version_info, python_version, pytorch_version,
                   use_gpu, run_test, annotation_tool, workspace_dir):
        """新部署任务开始时调用，覆盖任何旧状态。"""
        self.state = {
            'version': STATE_VERSION,
            'task_type': 'deploy',
            'status': 'in_progress',
            'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'yolo_name': version_info.get('name', ''),
            'version_info': version_info,
            'env_name': version_info.get('env_name', ''),
            'python_version': str(python_version or ''),
            'pytorch_version': str(pytorch_version or ''),
            'use_gpu': bool(use_gpu),
            'run_test': bool(run_test),
            'annotation_tool': annotation_tool or '',
            'workspace_dir': workspace_dir or '',
            'completed_steps': [],
            'current_step': '',
            'download': None,
            'finished_files': {},
        }
        self._last_dl_save = 0.0
        self._last_dl_pct = -1
        self._save()
        return self.state

    def set_current_step(self, step):
        if self.state is None:
            return
        self.state['current_step'] = step
        self._save()

    def mark_step_done(self, step):
        if self.state is None:
            return
        steps = self.state.setdefault('completed_steps', [])
        if step not in steps:
            steps.append(step)
        self._save()

    # ---------- 下载进度 ----------

    def update_download(self, filename, path, current, total, force=False):
        """记录正在进行的下载（节流落盘）。

        force=True 用于下载开始/结束等关键时刻强制落盘。
        """
        if self.state is None:
            return
        pct = int(current * 100 / total) if total else -1
        now = time.time()
        if (not force and pct == self._last_dl_pct
                and now - self._last_dl_save < 1.5):
            return
        self._last_dl_pct = pct
        self._last_dl_save = now
        self.state['download'] = {
            'filename': filename,
            'path': path,
            'downloaded': int(current),
            'total': int(total),
        }
        self._save()

    def clear_download(self):
        if self.state is None:
            return
        self.state['download'] = None
        self._save()

    def record_finished_file(self, filename, path, size, sha256):
        """登记一个已完成下载的实体文件（用于恢复时校验一致性）。"""
        if self.state is None:
            return
        self.state.setdefault('finished_files', {})[filename] = {
            'path': path,
            'size': int(size),
            'sha256': sha256,
        }
        self.state['download'] = None
        self._save()

    # ---------- 一致性校验 ----------

    def verify_finished_files(self):
        """校验已登记文件（存在性 + 大小 + SHA256）。

        返回失效文件名列表，并将其从状态中剔除；若权重校验失败，
        同时撤销「下载模型权重」步骤的完成标记，恢复时会重新下载。
        """
        if not self.state:
            return []
        invalid = []
        files = self.state.get('finished_files') or {}
        for name, meta in list(files.items()):
            path = (meta or {}).get('path', '')
            ok = False
            try:
                if path and os.path.exists(path) \
                        and os.path.getsize(path) == meta.get('size'):
                    ok = sha256_of(path) == meta.get('sha256')
            except Exception:
                ok = False
            if not ok:
                invalid.append(name)
                del files[name]
        if invalid:
            steps = self.state.get('completed_steps') or []
            if '下载模型权重' in steps:
                steps.remove('下载模型权重')
            self._save()
        return invalid

    # ---------- 放弃任务 ----------

    def discard(self, log=None):
        """放弃未完成任务：删除未完成的下载（.part）、已登记的实体文件
        以及状态文件本身。返回已删除文件列表。

        注意：已创建的 Conda 环境和已克隆的源码目录不在此处删除
        （它们是有效成果，可在「管理虚拟环境」中按需清理）。
        """
        log = log or (lambda msg: None)
        removed = []
        st = self.state or self.load()
        targets = []
        if st:
            dl = st.get('download') or {}
            part_path = dl.get('path') or ''
            if part_path:
                targets.append(part_path)
                # 对应的正式文件（可能是坏文件残留）
                if part_path.endswith('.part'):
                    targets.append(part_path[:-5])
            for meta in (st.get('finished_files') or {}).values():
                p = (meta or {}).get('path', '')
                if p:
                    targets.append(p)

        for p in dict.fromkeys(targets):
            try:
                if os.path.exists(p):
                    os.remove(p)
                    removed.append(p)
                    log(f'已删除: {p}')
            except Exception as e:
                log(f'⚠️ 删除失败: {p}（{e}），可手动删除')

        self.clear()
        return removed
