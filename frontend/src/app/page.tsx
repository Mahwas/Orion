"use client";

import { useEffect, useState } from "react";
import { getAdvice, getUserConfig, checkout } from "@/lib/api";
import Link from "next/link";

export default function Dashboard() {
  const [advice, setAdvice] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial fetch
    Promise.all([getAdvice(), getUserConfig()]).then(([adv, conf]) => {
      setAdvice(adv);
      setConfig(conf);
      setLoading(false);
    }).catch(console.error);

    // Poll for updates (hackathon fast path)
    const interval = setInterval(async () => {
      try {
        const adv = await getAdvice();
        setAdvice(adv);
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const handleCheckout = async (itemName: string, price: number) => {
    try {
      const res = await checkout(itemName, price);
      // Mock stripe redirect
      window.location.href = res.url;
    } catch (e) {
      alert("Failed to create Stripe session.");
    }
  };

  if (loading) return <div className="p-8 text-black">Loading Dashboard...</div>;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-10 px-4 text-black">
      <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Sidebar: Budget Info */}
        <div className="col-span-1 space-y-6">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <h2 className="text-xl font-bold mb-4">Your Budget</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Current Balance</span>
                <span className="font-semibold">${config?.snapshot?.current_balance?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Discretionary</span>
                <span className="font-semibold text-green-600">${config?.snapshot?.discretionary_budget_remaining?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Upcoming Bills</span>
                <span className="font-semibold text-red-600">${config?.snapshot?.upcoming_bills_total?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between border-t pt-3 mt-3">
                <span className="text-gray-500">Days to Payday</span>
                <span className="font-semibold px-2 py-0.5 bg-gray-100 rounded text-sm">
                  {config?.snapshot?.days_until_payday} days
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <h2 className="text-xl font-bold mb-4">Agent Config</h2>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-gray-500 flex justify-between">
                  Strictness <span>{config?.memory?.strictness}</span>
                </label>
                <input type="range" min="0" max="1" step="0.1" readOnly value={config?.memory?.strictness} className="w-full mt-2" />
              </div>
            </div>
          </div>

          <Link href="/store" className="block text-center w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition-colors">
            Go to Mock Storefront
          </Link>
        </div>

        {/* Main Area: Agent Advice */}
        <div className="col-span-2 space-y-6">
          <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 min-h-[400px]">
            <h1 className="text-2xl font-bold mb-6">Agent Analysis</h1>

            {advice?.verdict === "PENDING" ? (
              <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                <p>Waiting for you to select an item to purchase...</p>
                <Link href="/store" className="mt-4 text-sm text-blue-500 underline">Browse Mock Store</Link>
              </div>
            ) : (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {/* Verdict Header */}
                <div className={`p-4 rounded-xl border ${advice?.verdict === "DISCOURAGE" ? 'bg-red-50 border-red-200 text-red-900' : 'bg-green-50 border-green-200 text-green-900'}`}>
                  <h2 className="text-3xl font-black mb-1">{advice?.verdict}</h2>
                  <p className="text-sm opacity-80">Confidence Score: {advice?.score}/100</p>
                </div>

                {/* Reasoning */}
                <div>
                  <h3 className="font-semibold mb-2">Why?</h3>
                  <ul className="list-disc pl-5 space-y-1 text-gray-600">
                    {advice?.reasons?.map((r: string, i: number) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>

                {/* Alternatives */}
                {advice?.alternatives?.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-3">Cheaper Alternatives</h3>
                    <div className="grid gap-3">
                      {advice.alternatives.map((alt: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center p-3 border rounded-lg hover:border-blue-300 cursor-pointer bg-gray-50" onClick={() => handleCheckout(alt.title, alt.price)}>
                          <span className="font-medium">{alt.title}</span>
                          <div className="flex items-center gap-4">
                            <span className="font-bold text-green-700">${alt.price.toFixed(2)}</span>
                            <button className="text-sm bg-black text-white px-3 py-1 rounded">Accept</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Proceed Anyway Action */}
                <div className="pt-6 border-t mt-8 flex flex-col sm:flex-row gap-4">
                  <button
                    onClick={() => handleCheckout("Original Item", 200)} // Mocking original price
                    className="flex-1 py-3 px-4 bg-gray-100 text-gray-700 hover:bg-gray-200 font-semibold rounded-xl text-center transition-colors"
                  >
                    Proceed with Original Purchase
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
