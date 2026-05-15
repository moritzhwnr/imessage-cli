import { CopyButton } from './_components/CopyButton'

// One-liner via uv. Pulls down the wheel from PyPI, drops a tool-isolated
// venv under ~/.local/share/uv/tools, and links `imessage-bridge` onto PATH.
const INSTALL_CMD = 'uv tool install imessage-bridge'

// Same one-liner, with the `[send]` extra — pulls imessage-mcp-send into the
// same tool venv so `imessage-bridge serve --send` works. Without the extra,
// the CLI stays read-only.
const INSTALL_SEND_CMD = "uv tool install 'imessage-bridge[send]'"

// Don't-have-uv hint. Astral's official installer.
const INSTALL_UV_CMD = 'curl -LsSf https://astral.sh/uv/install.sh | sh'

// Replace with the actual Poke recipe URL once it exists.
const POKE_RECIPE_URL = 'https://poke.com/r/Ul3VdrP5nIG'

// The CLI flow a new user runs after install.
const SIGNUP_FLOW = `imessage-bridge signup           # create account, save your API key
imessage-bridge serve --public   # spin up the tunnel and register it`

// What an existing user runs to mint a fresh API key.
const ROTATE_KEY_CMD = 'imessage-bridge new-key'

export default function Home() {
  return (
    <main
      style={{
        maxWidth: 1100,
        margin: '0 auto',
        padding: '80px 24px 120px',
      }}
    >
      <Hero />

      <section
        style={{
          marginTop: 64,
          display: 'grid',
          gap: 20,
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        }}
      >
        <Card>
          <CardHeader
            kicker="01"
            title="Install the CLI"
            sub="One command from PyPI. Runs locally — your messages never leave your Mac."
          />
          <CodeBlockWithCopy code={INSTALL_CMD} />
          <details>
            <summary style={summary}>
              Also want to <strong>send</strong> messages from your AI?
            </summary>
            <div style={{ marginTop: 10 }}>
              <CodeBlockWithCopy code={INSTALL_SEND_CMD} />
              <p style={hint}>
                The <code style={inlineCode}>[send]</code> extra installs the
                add-on into the same tool environment. <code style={inlineCode}>serve</code>{' '}
                then asks whether to enable the <code style={inlineCode}>send_message</code>{' '}
                tool — or pass <code style={inlineCode}>--send</code> /{' '}
                <code style={inlineCode}>--no-send</code> to skip the prompt.{' '}
                <strong>Irreversible writes</strong> — install only if you understand the risk.
              </p>
            </div>
          </details>
          <details>
            <summary style={summary}>Don&apos;t have <code style={inlineCode}>uv</code>?</summary>
            <div style={{ marginTop: 10 }}>
              <CodeBlockWithCopy code={INSTALL_UV_CMD} />
              <p style={hint}>
                Official Astral installer. Adds Python 3.13 automatically if missing.
              </p>
            </div>
          </details>
          <a
            href="https://github.com/moritzhwnr/imessage-cli"
            style={ghostLink}
            target="_blank"
            rel="noreferrer"
          >
            View on GitHub →
          </a>
        </Card>

        <Card>
          <CardHeader
            kicker="02"
            title="Sign up and run"
            sub="All auth happens in your terminal. No web form, no session cookies."
          />
          <CodeBlockWithCopy code={SIGNUP_FLOW} />
          <p style={hint}>
            The CLI prints a Claude/Cursor/Poke config block with your
            personal MCP URL and API key. Copy it into your AI client of choice.
          </p>
          <details style={{ marginTop: 4 }}>
            <summary style={summary}>Lost your API key? Rotate it.</summary>
            <div style={{ marginTop: 10 }}>
              <CodeBlockWithCopy code={ROTATE_KEY_CMD} />
              <p style={hint}>
                Asks for your email + password, mints a new key, and overwrites
                the local one. Old keys keep working until you revoke them.
              </p>
            </div>
          </details>
        </Card>

        <Card>
          <CardHeader
            kicker="03"
            title="Plug into Poke"
            sub="One-click recipe to wire this MCP server into Poke."
          />
          <a href={POKE_RECIPE_URL} target="_blank" rel="noreferrer" style={primaryLink}>
            Open Poke recipe →
          </a>
          <ol style={pokeSteps}>
            <li>
              Click <strong>Open Poke recipe</strong> above. Poke will ask for
              your <code style={inlineCode}>API key</code>.
            </li>
            <li>
              Back in your terminal, copy the key from the panel printed by{' '}
              <code style={inlineCode}>imessage-bridge serve --public</code>.
              Lost it? Run <code style={inlineCode}>imessage-bridge new-key</code>{' '}
              to mint a fresh one.
            </li>
            <li>Paste it into Poke and save. That&apos;s it.</li>
          </ol>
          <p style={hint}>
            Don&apos;t use Poke? The same URL + key works in Claude Desktop,
            Cursor, and any other MCP-capable client.
          </p>
        </Card>
      </section>

      <Footer />
    </main>
  )
}

function Hero() {
  return (
    <header style={{ textAlign: 'center' }}>
      <div style={statusPill}>
        <span style={pillDot} />
        Bring-your-own-data MCP
      </div>
      <h1 style={h1}>
        Your iMessages,
        <br />
        where your AI lives.
      </h1>
      <p style={subtitle}>
        <code style={inlineCode}>imessage-bridge</code> exposes your local iMessage
        history to any MCP-capable AI — Claude, Poke, Cursor — through a stable
        broker URL. Messages never leave your Mac. The broker is just plumbing.
      </p>
    </header>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      {children}
    </div>
  )
}

function CardHeader({
  kicker,
  title,
  sub,
}: {
  kicker: string
  title: string
  sub: string
}) {
  return (
    <div>
      <div style={kickerStyle}>{kicker}</div>
      <h2 style={h2}>{title}</h2>
      <p style={cardSub}>{sub}</p>
    </div>
  )
}

function CodeBlockWithCopy({ code }: { code: string }) {
  return (
    <div style={{ position: 'relative' }}>
      <pre style={codeBlock}>{code}</pre>
      <div style={{ position: 'absolute', top: 10, right: 10 }}>
        <CopyButton text={code} />
      </div>
    </div>
  )
}

function Footer() {
  return (
    <footer style={footerStyle}>
      Built with Next.js + Supabase. Messages stay on your Mac.
    </footer>
  )
}

// ---------- shared inline styles ----------
const statusPill: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '6px 12px',
  background: 'rgba(10, 132, 255, 0.1)',
  border: '1px solid rgba(10, 132, 255, 0.25)',
  borderRadius: 999,
  fontSize: 12,
  color: 'var(--accent)',
  fontWeight: 500,
  marginBottom: 24,
}

const pillDot: React.CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: '50%',
  background: 'var(--success)',
  boxShadow: '0 0 8px var(--success)',
}

const h1: React.CSSProperties = {
  fontSize: 'clamp(40px, 7vw, 72px)',
  fontWeight: 700,
  letterSpacing: -1.5,
  lineHeight: 1.05,
  marginBottom: 20,
  background:
    'linear-gradient(180deg, var(--text) 0%, rgba(245, 245, 247, 0.6) 100%)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
}

const subtitle: React.CSSProperties = {
  fontSize: 18,
  color: 'var(--text-dim)',
  maxWidth: 580,
  margin: '0 auto',
  lineHeight: 1.55,
}

const kickerStyle: React.CSSProperties = {
  fontSize: 11,
  fontFamily: 'var(--font-geist-mono), monospace',
  color: 'var(--accent)',
  marginBottom: 6,
  letterSpacing: 1,
}

const h2: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 600,
  marginBottom: 4,
  letterSpacing: -0.5,
}

const cardSub: React.CSSProperties = {
  color: 'var(--text-dim)',
  fontSize: 14,
}

const inlineCode: React.CSSProperties = {
  padding: '2px 6px',
  background: 'rgba(255, 255, 255, 0.06)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  fontSize: '0.9em',
  fontFamily: 'var(--font-geist-mono), monospace',
}

const codeBlock: React.CSSProperties = {
  padding: '14px 16px',
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 12,
  color: 'var(--text)',
  overflow: 'auto',
  whiteSpace: 'pre',
  lineHeight: 1.55,
  fontFamily: 'var(--font-geist-mono), monospace',
}

const ghostLink: React.CSSProperties = {
  alignSelf: 'flex-start',
  padding: '8px 12px',
  fontSize: 13,
  color: 'var(--text-dim)',
  border: '1px solid var(--border)',
  borderRadius: 8,
}

const primaryLink: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  padding: '12px 16px',
  background: 'var(--accent)',
  color: 'white',
  fontWeight: 600,
  fontSize: 14,
  borderRadius: 8,
}

const hint: React.CSSProperties = {
  color: 'var(--text-faint)',
  fontSize: 12,
  lineHeight: 1.55,
}

const hintList: React.CSSProperties = {
  listStyle: 'none',
  color: 'var(--text-dim)',
  fontSize: 13,
  lineHeight: 1.8,
  paddingLeft: 4,
}

const pokeSteps: React.CSSProperties = {
  color: 'var(--text-dim)',
  fontSize: 13,
  lineHeight: 1.65,
  paddingLeft: 20,
  margin: 0,
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
}

const summary: React.CSSProperties = {
  cursor: 'pointer',
  color: 'var(--text-dim)',
  fontSize: 13,
  padding: '6px 0',
}

const footerStyle: React.CSSProperties = {
  marginTop: 80,
  paddingTop: 32,
  borderTop: '1px solid var(--border)',
  textAlign: 'center',
  color: 'var(--text-faint)',
  fontSize: 13,
}
