"use client";

export const CREDIT_BALANCE_EVENT = "vip:credits-balance-changed";

export type CreditBalanceEventDetail = {
  balance?: number | null;
  source?: string;
};

export function emitCreditBalanceChanged(detail: CreditBalanceEventDetail = {}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<CreditBalanceEventDetail>(CREDIT_BALANCE_EVENT, { detail }));
}

export function onCreditBalanceChanged(
  callback: (detail: CreditBalanceEventDetail) => void,
): () => void {
  if (typeof window === "undefined") return () => {};

  const handler = (event: Event) => {
    const customEvent = event as CustomEvent<CreditBalanceEventDetail>;
    callback(customEvent.detail || {});
  };

  window.addEventListener(CREDIT_BALANCE_EVENT, handler as EventListener);
  return () => {
    window.removeEventListener(CREDIT_BALANCE_EVENT, handler as EventListener);
  };
}
