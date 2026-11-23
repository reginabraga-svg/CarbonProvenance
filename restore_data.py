"""Restore versioned replication inputs from the data release asset."""
from pathlib import Path
from zipfile import ZipFile
from urllib.request import urlopen
import argparse,hashlib,json,shutil,tempfile

ROOT=Path(__file__).resolve().parent
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def restore(archive):
 manifest=json.loads((ROOT/'data_release_manifest.json').read_text(encoding='utf-8'))
 if digest(archive)!=manifest['archive_sha256']:
  raise ValueError('The data archive checksum does not match this release')
 expected=manifest['files']
 with ZipFile(archive) as z:
  if set(z.namelist())!=set(expected):
   raise ValueError('The archive file list does not match the release manifest')
  for name,record in expected.items():
   target=(ROOT/name).resolve()
   if not target.is_relative_to(ROOT):raise ValueError('Invalid destination path')
   if target.exists():
    if digest(target)!=record['sha256']:
     raise ValueError('A different file already exists: '+name)
    print('Verified existing file: '+name)
    continue
   target.parent.mkdir(parents=True,exist_ok=True)
   temporary=target.with_name(target.name+'.part')
   try:
    h=hashlib.sha256();size=0
    with z.open(name) as incoming,temporary.open('wb') as output:
     for chunk in iter(lambda:incoming.read(1024*1024),b''):
      h.update(chunk);size+=len(chunk);output.write(chunk)
    if size!=record['bytes'] or h.hexdigest()!=record['sha256']:
     raise ValueError('The extracted file checksum does not match: '+name)
    temporary.replace(target)
   finally:
    if temporary.exists():temporary.unlink()
   print('Restored: '+name)
 print('All '+str(len(expected))+' data files match this release')

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 inputs=parser.add_mutually_exclusive_group(required=True)
 inputs.add_argument('--archive',type=Path,help='Path to the downloaded data ZIP')
 inputs.add_argument('--url',help='HTTPS download URL of the data release asset')
 args=parser.parse_args()
 if args.archive:restore(args.archive.resolve())
 else:
  if not args.url.startswith('https://'):parser.error('Use an HTTPS URL')
  with tempfile.TemporaryDirectory(prefix='article_c_data_') as temporary:
   path=Path(temporary)/'data.zip'
   with urlopen(args.url,timeout=120) as response,path.open('wb') as output:shutil.copyfileobj(response,output)
   restore(path)
if __name__=='__main__':main()
