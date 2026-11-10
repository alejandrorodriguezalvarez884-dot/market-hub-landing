// The sign-out page (views/SignOut.astro), where the tools on the hub's subdomains send a member
// who wants to sign out: the session is the portal's cookie, and only the portal clears it.
import { words } from ".";

export const signout = words(
  {
    title: "Sign out",
    description: "Sign out of The Market Hub on this browser.",
    h1: "Sign out of The Market Hub?",
    lede: "You will be signed out on this browser, here and in every tool that uses this account (Bot League, Fundamentals Lab and the rest).",
    signOut: "Sign out",
    cancel: "Cancel",
    leaving: "Signing you out…",
    failed: "Signing out did not work. Try again in a minute.",
  },
  {
    title: "Salir",
    description: "Salir de The Market Hub en este navegador.",
    h1: "¿Salir de The Market Hub?",
    lede: "Saldrás en este navegador, aquí y en todas las herramientas que usan esta cuenta (Bot League, Fundamentals Lab y las demás).",
    signOut: "Salir",
    cancel: "Cancelar",
    leaving: "Saliendo…",
    failed: "No se ha podido salir. Inténtalo de nuevo en un minuto.",
  },
);
