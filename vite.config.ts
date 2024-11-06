import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve, join } from 'path';

const PROJ_ROOT = "/usr/local/project/mtri-statmagic-web-dev";
const INPUT_DIR = `${PROJ_ROOT}/static/react`;
const OUTPUT_DIR = `${INPUT_DIR}/dist`;

// const INPUT_DIR = "./static/react";
// const OUTPUT_DIR = "./static/react/dist";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Project root directory
  root: resolve(INPUT_DIR),
  // Base public path when served in development or production
  base: '/static',
  // config options when building/bundling application for production instead of development server
  build: {
    // manifest file name. manifest maps build.rollupOptions.input files to bundle
    manifest: "manifest.json",
    // Don't clear the output directory when React/Vite assets are built
    emptyOutDir: false,
    // output directory of build process
    outDir: resolve(OUTPUT_DIR),
    // Directly customize the underlying Rollup bundle
    rollupOptions: {
      // The bundle's entry point(s)
      input: {
        react: join(INPUT_DIR, '/js/info_component.tsx')
      }
    }
  }
})
