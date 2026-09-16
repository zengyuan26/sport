import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "蓝脑星球培训讲师工作台",
  description: "内部讲师 IP 诊断、受众判断与内容创作工作台。",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
