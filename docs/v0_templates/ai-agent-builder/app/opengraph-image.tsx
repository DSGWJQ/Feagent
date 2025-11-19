import { ImageResponse } from "next/og"

export const runtime = "edge"
export const alt = "AI Agent Builder - Visual workflow builder for AI SDK"
export const size = {
  width: 1200,
  height: 630,
}
export const contentType = "image/png"

export default async function Image() {
  return new ImageResponse(
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0a0a0a",
        backgroundImage:
          "radial-gradient(circle at 25px 25px, #1a1a1a 2%, transparent 0%), radial-gradient(circle at 75px 75px, #1a1a1a 2%, transparent 0%)",
        backgroundSize: "100px 100px",
      }}
    >
      {/* Main content */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px",
        }}
      >
        {/* Title */}
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            background: "linear-gradient(to bottom right, #ffffff, #a855f7)",
            backgroundClip: "text",
            color: "transparent",
            marginBottom: 24,
            textAlign: "center",
          }}
        >
          AI Agent Builder
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontSize: 32,
            color: "#a1a1aa",
            marginBottom: 60,
            textAlign: "center",
          }}
        >
          Visual workflow builder for AI SDK
        </div>

        {/* Visual representation of nodes */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 40,
          }}
        >
          {/* Node 1 */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: 140,
              height: 140,
              backgroundColor: "#18181b",
              border: "3px solid #a855f7",
              borderRadius: 16,
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 8 }}>📝</div>
            <div style={{ fontSize: 18, color: "#e4e4e7" }}>Prompt</div>
          </div>

          {/* Arrow */}
          <div style={{ fontSize: 48, color: "#a855f7" }}>→</div>

          {/* Node 2 */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: 140,
              height: 140,
              backgroundColor: "#18181b",
              border: "3px solid #3b82f6",
              borderRadius: 16,
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 8 }}>🤖</div>
            <div style={{ fontSize: 18, color: "#e4e4e7" }}>AI Model</div>
          </div>

          {/* Arrow */}
          <div style={{ fontSize: 48, color: "#3b82f6" }}>→</div>

          {/* Node 3 */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: 140,
              height: 140,
              backgroundColor: "#18181b",
              border: "3px solid #10b981",
              borderRadius: 16,
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 8 }}>🎨</div>
            <div style={{ fontSize: 18, color: "#e4e4e7" }}>Output</div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          display: "flex",
          alignItems: "center",
          gap: 12,
          color: "#71717a",
          fontSize: 24,
        }}
      >
        <span>Powered by AI SDK</span>
        <span>•</span>
        <span>Built with React Flow</span>
      </div>
    </div>,
    {
      ...size,
    },
  )
}
