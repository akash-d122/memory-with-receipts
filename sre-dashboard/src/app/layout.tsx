import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aegis SRE Dashboard | Blended RAG & Operational Memory",
  description:
    "Next-gen generative SRE troubleshooting dashboard integrating database incident memory with playbook runbooks. Zero-hallucination RAG with verifiable receipts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
