import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '192.168.50.145', // 绑定到局域网 IP，供同网段设备访问
    port: 5173,
  },
})
