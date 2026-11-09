import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const grotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["300", "400", "500", "700"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Vovage — fare intelligence",
  description:
    "Predict airfare before you book, and what a night will really cost you, before you pay.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#060607" },
    { media: "(prefers-color-scheme: light)", color: "#fafaf7" },
  ],
};

// theme must resolve before first paint — no flash, no flip
const themeBoot = `
(function () {
  var t;
  try { t = localStorage.getItem("vovage-theme"); } catch (e) {}
  if (t !== "light" && t !== "dark") t = "dark";
  document.documentElement.dataset.theme = t;
})();
`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <body className={`${grotesk.variable} ${inter.variable}`}>
        {/* theme must resolve before first paint — no flash, no flip */}
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
        {children}
      </body>
    </html>
  );
}
