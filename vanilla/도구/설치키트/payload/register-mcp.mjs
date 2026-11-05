// Register the globally installed kordoc MCP server with Claude Desktop (if present).
// Uses absolute paths to node and kordoc so the desktop app does not depend on PATH.
import { execSync } from "node:child_process"
import { existsSync, readFileSync, writeFileSync, copyFileSync } from "node:fs"
import { join } from "node:path"
import { homedir } from "node:os"

const globalRoot = execSync("npm root -g", { encoding: "utf8" }).trim()
const mcpScript = join(globalRoot, "kordoc", "dist", "mcp.js")
if (!existsSync(mcpScript)) {
  console.error(`[kordoc] MCP script not found: ${mcpScript}`)
  process.exit(1)
}
const entry = { command: process.execPath, args: [mcpScript] }

// Print node path and script path (one per line) for the Claude Code CLI registration
if (process.argv.includes("--print")) {
  console.log(entry.command)
  console.log(entry.args[0])
  process.exit(0)
}

const home = homedir()
const desktopDir =
  process.platform === "win32" ? join(process.env.APPDATA ?? join(home, "AppData", "Roaming"), "Claude")
  : process.platform === "darwin" ? join(home, "Library", "Application Support", "Claude")
  : join(home, ".config", "Claude")
const configPath = join(desktopDir, "claude_desktop_config.json")

if (!existsSync(desktopDir)) {
  console.log("[kordoc] Claude Desktop not found; skipped desktop registration.")
  process.exit(0)
}

let config = {}
if (existsSync(configPath)) {
  // Keep a backup before touching the user's config
  copyFileSync(configPath, configPath + ".bak")
  try {
    config = JSON.parse(readFileSync(configPath, "utf8") || "{}")
  } catch {
    console.error(`[kordoc] Could not parse ${configPath}; left unchanged (backup: .bak).`)
    process.exit(1)
  }
}
config.mcpServers = { ...(config.mcpServers ?? {}), kordoc: entry }
writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n", "utf8")
console.log(`[kordoc] Registered in Claude Desktop: ${configPath}`)
