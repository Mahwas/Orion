const API_BASE = "http://localhost:8000/api/v1";

export interface PurchaseContext {
    source: string;
    timestamp: string;
    merchant: string;
    product_title: string;
    price: number;
    currency: string;
    category_hint: string;
    url: string;
    user_intent_hint: string;
    image_crop_ref?: string;
}

export async function sendPurchaseContext(context: PurchaseContext) {
    const res = await fetch(`${API_BASE}/context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(context),
    });
    if (!res.ok) throw new Error('Failed to send context');
    return res.json();
}

export async function getAdvice() {
    const res = await fetch(`${API_BASE}/advice`);
    if (!res.ok) throw new Error('Failed to fetch advice');
    return res.json();
}

export async function getUserConfig() {
    const res = await fetch(`${API_BASE}/user/config`);
    if (!res.ok) throw new Error('Failed to fetch user config');
    return res.json();
}

export async function checkout(itemName: string, price: number) {
    const res = await fetch(`${API_BASE}/checkout?item_name=${encodeURIComponent(itemName)}&price=${price}`, {
        method: "POST",
    });
    if (!res.ok) throw new Error('Failed to create checkout session');
    return res.json();
}
