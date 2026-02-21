"use client";

import { useState } from 'react';
import { sendPurchaseContext } from '@/lib/api';
import { useRouter } from 'next/navigation';

const PRODUCTS = [
    {
        id: 1,
        title: "Sony WH-1000XM5 Noise Canceling Headphones",
        price: 348.00,
        merchant: "Amazon",
        category: "electronics",
        imageUrl: "https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?q=80&w=400&auto=format&fit=crop"
    },
    {
        id: 2,
        title: "Nike Air Max 270",
        price: 160.00,
        merchant: "Nike Store",
        category: "apparel",
        imageUrl: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=400&auto=format&fit=crop"
    },
    {
        id: 3,
        title: "Dune Messiah - Paperback Edition",
        price: 9.99,
        merchant: "Barnes & Noble",
        category: "books",
        imageUrl: "https://images.unsplash.com/photo-1541963463532-d68292c34b19?q=80&w=400&auto=format&fit=crop"
    },
    {
        id: 4,
        title: "OLED Gaming Monitor 27\"",
        price: 899.99,
        merchant: "BestBuy",
        category: "electronics",
        imageUrl: "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?q=80&w=400&auto=format&fit=crop"
    }
];

export default function StorePage() {
    const [loadingId, setLoadingId] = useState<number | null>(null);
    const router = useRouter();

    const handleBuyIntent = async (product: typeof PRODUCTS[0]) => {
        setLoadingId(product.id);

        const context = {
            source: "simulated_storefront",
            timestamp: new Date().toISOString(),
            merchant: product.merchant,
            product_title: product.title,
            price: product.price,
            currency: "USD",
            category_hint: product.category,
            url: `https://example.com/item/${product.id}`,
            user_intent_hint: "buy"
        };

        try {
            await sendPurchaseContext(context);
            // Head to the main dashboard to view the agent's advice
            router.push("/");
        } catch (err) {
            console.error(err);
            alert("Failed to reach backend API. Is it running?");
        } finally {
            setLoadingId(null);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-5xl mx-auto">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">Simulated Storefront</h1>
                <p className="text-gray-500 mb-8">Click &quot;Buy Now&quot; to trigger the Orion purchase interception flow.</p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {PRODUCTS.map((prod) => (
                        <div key={prod.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                            <div
                                className="h-48 w-full bg-cover bg-center"
                                style={{ backgroundImage: `url(${prod.imageUrl})` }}
                            />
                            <div className="p-4 flex flex-col flex-grow text-black">
                                <div className="text-xs font-semibold text-gray-400 mb-1">{prod.merchant}</div>
                                <h3 className="font-semibold text-gray-800 leading-tight mb-2 flex-grow">{prod.title}</h3>
                                <div className="text-lg font-bold mb-4">${prod.price.toFixed(2)}</div>

                                <button
                                    onClick={() => handleBuyIntent(prod)}
                                    disabled={loadingId !== null}
                                    className="w-full py-2 px-4 bg-black text-white rounded-lg font-medium hover:bg-gray-800 transition-colors disabled:opacity-50"
                                >
                                    {loadingId === prod.id ? "Analyzing..." : "Buy Now"}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
