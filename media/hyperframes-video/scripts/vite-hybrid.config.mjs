import {defineConfig} from 'vite';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export default defineConfig({root,build:{outDir:path.join(root,'assets'),emptyOutDir:false,lib:{entry:path.join(root,'scripts/hybrid-3d.js'),name:'SightCheckHybrid',formats:['iife'],fileName:()=> 'hybrid-3d.js'},minify:true}});
