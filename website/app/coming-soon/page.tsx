import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Growth Academy | Updates in Progress",
  robots: { index: false, follow: false },
};

export default function ComingSoonPage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "2rem",
        background: "#0f172a",
        color: "#f8fafc",
        fontFamily:
          "Roboto, system-ui, -apple-system, Segoe UI, sans-serif",
      }}
    >
      <img
        src="/icon.png"
        alt="My Growth Academy"
        width={72}
        height={72}
        style={{ marginBottom: "1.5rem", borderRadius: "16px" }}
      />
      <h1
        style={{
          fontFamily: "Poppins, system-ui, sans-serif",
          fontSize: "clamp(1.75rem, 4vw, 2.75rem)",
          fontWeight: 700,
          margin: 0,
        }}
      >
        Updates in progress.
      </h1>
      <p
        style={{
          fontSize: "clamp(1.1rem, 2.5vw, 1.5rem)",
          color: "#94a3b8",
          marginTop: "0.75rem",
        }}
      >
        Coming soon.
      </p>
      <p style={{ marginTop: "2rem", color: "#64748b", fontSize: "0.95rem" }}>
        My Growth Academy
      </p>
    </main>
  );
}
