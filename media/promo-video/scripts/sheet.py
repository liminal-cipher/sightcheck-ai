"""QC용 컨택트 시트: out/stills/*.png를 3×2로 묶어 out/sheets/에 저장한다."""
import glob, os, subprocess, sys

src = sys.argv[1] if len(sys.argv) > 1 else 'out/stills'
dst = sys.argv[2] if len(sys.argv) > 2 else 'out/sheets'
files = sorted(glob.glob(f'{src}/*.png'))
os.makedirs(dst, exist_ok=True)
for f in glob.glob(f'{dst}/*.png'):
    os.remove(f)
for n in range(0, len(files), 6):
    chunk = files[n:n + 6]
    args, filt = [], ''
    for i in range(6):
        if i < len(chunk):
            args += ['-i', chunk[i]]
        else:
            args += ['-f', 'lavfi', '-i', 'color=black:s=1920x1080:d=1']
        filt += f'[{i}:v]scale=960:540[v{i}];'
    filt += ''.join(f'[v{i}]' for i in range(6)) + 'xstack=inputs=6:layout=0_0|w0_0|0_h0|w0_h0|0_h0+h1|w0_h0+h1[out]'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *args, '-filter_complex', filt, '-map', '[out]', '-frames:v', '1', f'{dst}/sheet{n // 6}.png'], check=True)
    print(f'{dst}/sheet{n // 6}.png', ' '.join(os.path.basename(c)[1:-4] for c in chunk))
