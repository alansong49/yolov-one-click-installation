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
    asset_path = r'e:\程序\一键安装 yolov\Linux一键安装.sh'

    if not os.path.exists(asset_path):
        print(f"❌ 文件不存在: {asset_path}")
        sys.exit(1)

    file_size = os.path.getsize(asset_path)
    print(f"文件: {asset_path}")
    print(f"大小: {file_size / (1024):.2f} KB")

    api = GhApi(owner=owner, repo=repo, token=token)

    try:
        tag_name = f'v{time.strftime("%Y%m%d")}'
        
        print(f"查找 Release: {tag_name}")
        releases = await api.repos.list_releases(owner=owner, repo=repo)
        release = None
        for r in releases:
            if r.tag_name == tag_name:
                release = r
                print(f"找到现有 Release: {release.html_url}")
                break
        
        if not release:
            print(f"❌ 未找到 Release: {tag_name}")
            sys.exit(1)

        upload_url = release.upload_url.replace('{?name,label}', '')
        asset_name = os.path.basename(asset_path)
        
        print("检查是否已存在同名文件...")
        assets = await api.repos.list_release_assets(owner=owner, repo=repo, release_id=release.id)
        for asset in assets:
            if asset.name == asset_name:
                print(f"⚠️  删除旧文件: {asset.name}")
                await api.repos.delete_release_asset(owner=owner, repo=repo, asset_id=asset.id)
                break
        
        print(f"上传文件: {asset_path}")
        with open(asset_path, 'rb') as f:
            asset_data = f.read()
        
        headers = {
            'Authorization': f'token {token}',
            'Content-Type': 'application/octet-stream',
        }
        
        timeout = httpx.Timeout(300.0, connect=30.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{upload_url}?name={asset_name}",
                headers=headers,
                content=asset_data
            )
        
        if response.status_code == 201:
            print(f"✅ 文件上传成功: {response.json()['browser_download_url']}")
            print("\n🎉 上传完成！")
        else:
            print(f"❌ 上传失败: {response.status_code} - {response.text}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
