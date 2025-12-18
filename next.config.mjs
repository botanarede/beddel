import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  transpilePackages: ["beddel"],
  webpack: (config) => {
    // Toggle local package via env. Default (unset) uses npm-installed "beddel".
    if (process.env.BEDDEL_LOCAL === "1") {
      config.resolve.alias = config.resolve.alias || {}
      config.resolve.alias["beddel"] = path.join(__dirname, "packages/beddel/src")
    }
    return config
  },
}

export default nextConfig
