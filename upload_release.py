import os
import sys
import time
import asyncio
from ghapi.core import GhApi
import httpx


def get_github_token():
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    return None


async def main():
    token = get_github_token()
    if not token:
        print("❌ 未提供 GitHub Token")
        sys.exit(1)

    owner = 'alansong49'
    repo = 'yolov-one-click-installation'
    asset_path = r'e:\程序\一键安装 yolov\dist\YOLO_AutoInstaller.exe'

    if not os.path.exists(asset_path):
        print(f"❌ 文件不存在: {asset_path}")
        sys.exit(1)

    file_size = os.path.getsize(asset_path)
    print(f"文件: {asset_path}")
    print(f"大小: {file_size / (1024 * 1024):.2f} MB")

    api = GhApi(owner=owner, repo=repo, token=token)

    try:
        tag_name = f'v{time.strftime("%Y%m%d")}'
        release_name = f'YOLO AutoInstaller {time.strftime("%Y-%m-%d")}'
        body = f"""
YOLO AutoInstaller - 一键安装工具

**更新内容:**
- 修复日志乱码问题
- 修复 Linux 版本 Miniconda3 安装后重启终端找不到 conda 的问题
- 新增全局扫描 Conda 功能
- 更新图标

**文件:**
- YOLO_AutoInstaller.exe ({file_size / (1024 * 1024):.1f} MB)
"""
        print(f"创建 Release: {tag_name}")
        try:
            release = await api.repos.create_release(
                owner=owner,
                repo=repo,
                tag_name=tag_name,
                name=release_name,
                body=body,
                draft=False,
                prerelease=False
            )
            print(f"Release 创建成功: {release.html_url}")
        except Exception as e:
            print(f"Release 可能已存在，尝试获取现有 Release: {e}")
            releases = await api.repos.list_releases(owner=owner, repo=repo)
            release = None
            for r in releases:
                if r.tag_name == tag_name:
                    release = r
                    print(f"找到现有 Release: {release.html_url}")
                    break
            if not release:
                raise

        upload_url = release.upload_url.replace('{?name,label}', '')
        asset_name = os.path.basename(asset_path)
        
        print(f"上传文件: {asset_path}")
        with open(asset_path, 'rb') as f:
            asset_data = f.read()
        
        headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/octet-stream',
        }
        
        timeout = httpx.Timeout(300.0, connect=30.0)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{upload_url}?name={asset_name}",
                        headers=headers,
                        content=asset_data
                    )
                
                if response.status_code == 201:
                    print(f"✅ 文件上传成功: {response.json()['browser_download_url']}")
                    print("\n🎉 上传完成！")
                    return
                elif response.status_code == 422:
                    print("⚠️  文件可能已存在，删除旧文件并重试...")
                    assets = await api.repos.list_release_assets(owner=owner, repo=repo, release_id=release.id)
                    for asset in assets:
                        if asset.name == asset_name:
                            await api.repos.delete_release_asset(owner=owner, repo=repo, asset_id=asset.id)
                            print(f"已删除旧文件: {asset.name}")
                            continue
                else:
                    print(f"❌ 上传失败: {response.status_code} - {response.text}")
            except httpx.ReadTimeout:
                print(f"⚠️  第 {attempt + 1}/{max_retries} 次超时，重试中...")
                time.sleep(5)
            except Exception as e:
                print(f"❌ 第 {attempt + 1}/{max_retries} 次出错: {e}")
                time.sleep(5)
        
        print("\n❌ 所有重试均失败")
        sys.exit(1)

    except Exception as e:
        print(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
