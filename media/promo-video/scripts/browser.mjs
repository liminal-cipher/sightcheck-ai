// 캡처용 Chromium 설정. WebGL은 SwiftShader(CPU)로, 페이지 합성은 CPU 래스터로 돌린다(GPU 합성보다 ~25% 빠름).
import { chromium } from 'playwright-core';

export const launch = () => chromium.launch({
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-compositing',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding'],
});
