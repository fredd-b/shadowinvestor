import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShadowInvestor",
  description: "Personal catalyst-driven trading signal system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body className="min-h-full bg-zinc-950 text-zinc-100 antialiased">
        {children}
      </body>
    </html>
  );
}
