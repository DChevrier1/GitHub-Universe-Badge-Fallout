#!/usr/bin/env python3
"""Build a portable app-only ZIP with Python's standard library."""
import ast
import io
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent
APP=ROOT/'apps'/'fallout'
FILES=['__init__.py', 'assets/ATTRIBUTION.md', 'assets/COLOR_PROMPT.md', 'assets/vault-boy-color-sheet.png', 'assets/vault-boy.gif', 'companion.py', 'core.py', 'data.py', 'font5x7.py', 'fontvector.py', 'icon.png', 'mascot.py']
DOCS=['README.md', 'NOTICE.md', 'EFFECTS.md']
def build():
    destination=ROOT/'dist'
    if destination.is_symlink():raise ValueError('Build directory must not be a symlink')
    destination.mkdir(exist_ok=True)
    output=destination/(APP.name+'-badge.zip')
    if output.is_symlink():raise ValueError('Build output must not be a symlink')
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in FILES:
            path=APP/name
            if any(part.is_symlink() for part in (path, *path.parents) if part != ROOT.parent):raise ValueError('Symlink in package: '+name)
            data=path.read_bytes()
            if path.suffix=='.py':
                tree=ast.parse(data.decode())
                for node in ast.walk(tree):
                    if isinstance(node,(ast.Module,ast.FunctionDef,ast.ClassDef)) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
                        node.body.pop(0)
                        if not node.body:node.body.append(ast.Pass())
                data=(ast.unparse(tree)+'\n').encode()
                compile(data,name,'exec')
            archive.writestr('apps/'+APP.name+'/'+name,data)
        archive.writestr('INSTALL.txt','Copy only apps/'+APP.name+' to the BADGER apps directory. Back up any existing custom app first. Keep every other file, especially secrets.py. Eject safely and restart. See README.md for full instructions.\n')
        for name in DOCS:
            path=ROOT/name
            if path.is_symlink():raise ValueError('Symlink in documentation: '+name)
            archive.writestr(name,path.read_bytes())
    output.write_bytes(buffer.getvalue())
    print(output)
    return output
if __name__=='__main__':build()
