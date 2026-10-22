from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
backup=root/'capture/dark-v3-index.html'
if not backup.exists(): backup.write_bytes((root/'index.html').read_bytes())
original=backup.read_text(encoding='utf-8')
s=original
colors={'#12161ce8':'#f7f8f5f5','#12161c':'#f7f8f5','#f4f5f3':'#20252b','#aeb8ba':'#596168','#222c22':'#c7ef7b','#56604d':'#b7c4a3','#394047':'#d8ddd5','#1a2027':'#ffffff','#465049':'#d0d7cd','#58614f':'#cdd5c8'}
for a,b in colors.items(): s=s.replace(a,b)
# The original lime remains the fill/border accent; its text shade darkens for white-ground contrast.
s=s.replace('color:#c7ef7b','color:#49651e')
s=s.replace('color:#ffae79','color:#98501c')
s=s.replace('</style>','#measure-source{background:#f7f8f5}.pill{color:#263513}.brand b{color:#49651e}</style>')
# Verify that visible copy, all scripts, dimensions and timing are untouched.
scripts=lambda x:re.findall(r'<script[^>]*>.*?</script>',x,re.S)
assert scripts(s)==scripts(original)
text=lambda x: re.sub(r'<[^>]+>','',re.sub(r'<style>.*?</style>|<script[^>]*>.*?</script>','',x,flags=re.S))
assert text(s)==text(original)
(root/'index.html').write_text(s,encoding='utf-8')
p=root/'scripts/hybrid-3d.js';js=p.read_text(encoding='utf-8')
needle='const host=document.getElementById(\'hybrid-canvas\');v.mount(host);'
addition="\n// Light-mode canvas surround only; viewport scene, materials and camera remain unchanged.\nconst originalClearColor=v.renderer.setClearColor.bind(v.renderer);\nv.renderer.setClearColor=(color,alpha)=>originalClearColor('#f7f8f5',alpha);"
if addition not in js:
    assert needle in js
    (root/'capture/dark-v3-hybrid-3d.js').write_text(js,encoding='utf-8')
    p.write_text(js.replace(needle,needle+addition),encoding='utf-8')
print('Light palette applied. Copy, timelines, layout, cameras and venue content retained.')
