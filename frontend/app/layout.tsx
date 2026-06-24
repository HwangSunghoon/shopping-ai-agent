import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shopping AI Agent",
  description: "AI 추천이 자연스럽게 녹아든 쇼핑 검색 MVP",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
