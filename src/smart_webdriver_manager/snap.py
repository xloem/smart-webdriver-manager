import platform
import requests
from .utils import download_file

from dissect.squashfs import SquashFS

if __name__ == '__main__':
    chromium_info = requests.get('http://api.snapcraft.io/v2/snaps/info/chromium', headers={'Snap-Device-Series':'16'}).json()
    import pdb; pdb.set_trace()
    archs = {
        channel['channel']['architecture']: {
            'version': channel['version'],
            'url': channel['download']['url'],
        }
        for channel in chromium_info['channel-map']
        if channel['channel']['name'] == 'stable'
    }
    
    arch = {
        'x86_64': 'amd64',
        # : arm64, armhf, i386
    }[platform.machine()]
    version, url = archs[arch].values()
    
    with (
        download_file(url) as snap_path,
        open(snap_path, 'rb') as snap_fh
    ):
        snap = SquashFS(snap_fh)
        queue = []
        name, inode = ('', snap.get('/'))
        while True:
            if inode.is_dir():
                queue.extend([
                    ((name, inode), item)
                    for item in inode.listdir().items()
                ])
            else:
                print(name)
            if not len(queue):
                break
            (parent_name, parent_inode), (name, inode) = queue.pop()
            name = parent_name + '/' + name
