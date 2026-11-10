import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Vovage — Where to next?",
  description:
    "The world, within reach. Begin your journey with Vovage.",
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
      <body className={`${playfair.variable} ${inter.variable}`}>
        {/* theme must resolve before first paint — no flash, no flip */}
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
        {children}
      </body>
    </html>
  );
}
