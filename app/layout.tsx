import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Crypto Open-Data Anomaly Detector',
  description:
    'Statistical anomaly detection over CoinGecko public market data. Rolling z-scores, volume spikes and volatility regime changes. Not machine learning, not a price prediction.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-950 text-slate-200 antialiased">{children}</body>
    </html>
  );
}
