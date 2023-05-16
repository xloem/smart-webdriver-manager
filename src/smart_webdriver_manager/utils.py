import os
import zipfile
import shutil
import tempfile
import requests
import backoff
import platform
import tqdm
from contextlib import contextmanager
#from dissect.squashfs import SquashFS
from poorly_done_squashfs_tools import unsquashfs
from urllib.parse import urlparse, unquote
from pathlib import Path
from packaging.version import parse, Version

from . import logger


class LinuxZipFileWithPermissions(zipfile.ZipFile):
    """Class for extract files in linux with right permissions
    https://stackoverflow.com/a/54748564
    """

    def _extract_member(self, member, targetpath=None, pwd=None):
        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)
        if targetpath is None:
            targetpath = os.getcwd()
        target = super()._extract_member(member, targetpath, pwd)
        attr = member.external_attr >> 16
        if attr != 0:
            os.chmod(target, attr)
        return target


def unpack_zip(zip_path):
    """Unzip zip to same diretory"""
    zip_class = zipfile.ZipFile if platform.system() == "Windows" else LinuxZipFileWithPermissions
    archive = zip_class(zip_path)
    try:
        archive.extractall(Path(zip_path).parent)
    except Exception as e:
        if e.args[0] not in [26, 13] and e.args[1] not in ["Text file busy", "Permission denied"]:
            raise e
    return archive.namelist()


def unpack_squashfs(squashfs_path):
    """Unpack squashfs to same directory"""
    folder = str(Path(squashfs_path).parent)
    unsquashfs('-dest', folder, '-quiet', str(squashfs_path))
    namelist = []
    for dirpath, dirnames, filenames in os.walk(folder):
        namelist.extend([os.path.join(dirpath, name) for name in filenames])
    return namelist
    #namelist = []
    #queue = []
    #with open(squashfs_path, "rb") as fh:
    #    archive = SquashFS(fh)
    #    import pdb; pdb.set_trace()
    #    total = sum([inode.size for inode in tqdm.tqdm(archive.iter_inodes(), total=archive.sb.inodes) if inode.is_file()])
    #    with tqdm.tqdm(total=total, desc="unsquashfs", leave=False, unit='B', unit_scale=True) as p:
    #        parent = Path(squashfs_path).parent
    #        path, inode = (Path(''), archive.get('/'))
    #        while True:
    #            p.desc = str(path)
    #            if inode.is_dir():
    #                queue.extend([
    #                    ((path, inode), item)
    #                    for item in inode.listdir().items()
    #                ])
    #                (parent/path).mkdir(parents=True, exist_ok=True)
    #            elif inode.is_symlink():
    #                (parent/path).symlink_to(inode.link)
    #            else:
    #                total = inode.size
    #                chunk = 16 * 1024 * 1024
    #                with inode.open() as inf, open((parent/path), 'wb') as outf:
    #                    while buf := inf.read(chunk):
    #                        outf.write(buf)
    #                        p.update(len(buf))
    #                namelist.append(str(path))
    #            if not len(queue):
    #                break
    #            (parent_path, parent_inode), (path, inode) = queue.pop()
    #            path = parent_path / path
    #return namelist


@contextmanager
def download_file(url) -> Path:
    """Better download"""
    name = Path(urlparse(url).path).name
    with mktempdir() as tmpdir:

        @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=30)
        def get():
            with requests.get(url, stream=True) as r:
                save_path = tmpdir.joinpath(name)
                total = int(r.headers.get('content-length', 0))
                chunk = 16 * 1024 * 1024
                with open(save_path, "wb") as f, tqdm.tqdm(total=total, desc=name, unit='B', unit_scale=True) as p:
                    while buf := r.raw.read(chunk):
                        f.write(buf)
                        p.update(len(buf))
                return save_path

        yield get()


@contextmanager
def mktempdir() -> Path:
    """Having errors removing temp directories in Widnows..."""
    try:
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
    finally:

        @backoff.on_exception(backoff.expo, shutil.Error, max_time=10)
        def remove():
            shutil.rmtree(tmp, ignore_errors=False)
            logger.debug(f"Removed {tmp}")

        remove()
