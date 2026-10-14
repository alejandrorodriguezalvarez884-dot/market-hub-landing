// What Market Hub publishes outside the portal, as the Media page shows it. Kept by hand: a video
// is added here once it is on YouTube (its address is in the-market-hub-media, in the video's
// published.json), with a cover in site/public/media/ drawn by us, so that the page asks nothing
// of YouTube until a visitor presses play.

import { API, api } from "./api";

export interface Video {
  id: string; // YouTube's id of the video: youtu.be/<id>
  title: string;
  length: string; // as a clock: "4:16"
  cover: string; // a file in site/public/media/
  note?: string; // what it is, when it is not an episode: "Trailer"
}

export interface Playlist {
  name: string;
  about: string;
  url: string; // the playlist on YouTube; empty until it is known, and the channel is linked instead
  videos: Video[];
  shorts: Video[];
}

export const YOUTUBE = {
  channel: "https://www.youtube.com/@TheMarketHub-y7c",
  playlists: [
    {
      name: "Money 101",
      about: "How money really works, one idea at a time: first something you can picture, then the numbers.",
      url: "",
      videos: [
        { id: "mY6VaYSQmC0", title: "Money 101: how money really works, one idea at a time", length: "0:49", cover: "money-101-trailer.jpg", note: "Trailer" },
        { id: "VXJU88A1oJw", title: "Compound interest: why time matters more than the amount", length: "4:16", cover: "compound-interest.jpg", note: "Episode 1" },
        { id: "gSV_7yoBPF0", title: "Inflation: why the same money buys less every year", length: "4:33", cover: "inflation.jpg", note: "Episode 2" },
        { id: "nApfz535ZbM", title: "Debt: what borrowing really costs", length: "4:20", cover: "debt.jpg", note: "Episode 3" },
      ],
      shorts: [
        { id: "WKDiiXEf17A", title: "The credit card minimum that takes eleven years", length: "0:43", cover: "debt-short.jpg" },
        { id: "4LCtdOLN4DI", title: "The hundred-dollar bill that lost half its value in a drawer", length: "0:44", cover: "inflation-short.jpg" },
        { id: "B0TP-VL4Ov4", title: "The lily pad riddle most people get wrong", length: "0:41", cover: "compound-interest-short.jpg" },
        { id: "uQfP60v2Hts", title: "Nobody taught you this in school", length: "0:49", cover: "money-101-trailer-short.jpg" },
      ],
    },
  ] as Playlist[],
  // Playlists that are planned and have no video yet: shown as empty places, with no promise of what or when.
  upcoming: 2,
};

// Market Hub's account on Instagram. Its posts are not kept here: the page asks the portal for the
// latest ones (posts(), below).
export const INSTAGRAM = { handle: "the_market_hub_app" };

// A post of the account, whatever it is: a reel, a picture, an album.
export type Post = { id: string; code: string; url: string; kind: "reel" | "video" | "photo" | "album"; text: string; posted_utc: string;
  cover: { v: string; upright: boolean } };

// What the account last posted, newest first. The portal does not ask Instagram: the-market-hub-media
// reads the account's posts and publishes them into the portal's store, each with its cover, so
// this page asks nothing of Instagram either.
export const posts = (limit = 12) => api<{ posts: Post[]; handle: string; read_utc: string | null }>(`/api/public/instagram?limit=${limit}`);
// A cover's address names its version: a browser keeps it for good.
export const postCover = (p: Post) => `${API}/api/public/instagram/cover?id=${encodeURIComponent(p.id)}&v=${encodeURIComponent(p.cover.v)}`;
// Where a post is opened. Only an address on Instagram is followed; anything else leads to the account.
export const postUrl = (p: Post) => (/^https:\/\/www\.instagram\.com\/[A-Za-z0-9_\-\/.]+$/.test(p.url) ? p.url : `https://www.instagram.com/${INSTAGRAM.handle}/`);

// Market Hub's account on X. Its posts are not kept here either:
// the page asks the portal for the latest ones (xPosts(), below).
export const X = { handle: "the_market_hub_" };

// A post of the account on X: its text, exactly as it went out, and where it is.
export type XPost = { id: string; url: string; text: string; posted_utc: string };

// What the account last posted on X, newest first. the-market-hub-media writes and records each post
// and publishes the latest into the portal's store, so neither the portal nor this page asks X.
export const xPosts = (limit = 6) => api<{ posts: XPost[]; handle: string; read_utc: string | null }>(`/api/public/x?limit=${limit}`);
// Where a post is opened. Only an address of a post on X is followed; anything else leads to the account.
export const xPostUrl = (p: XPost, handle: string) =>
  /^https:\/\/x\.com\/[A-Za-z0-9_]{1,15}\/status\/[0-9]{5,25}$/.test(p.url) ? p.url : `https://x.com/${handle}`;

export const shortUrl = (id: string) => `https://www.youtube.com/shorts/${id}`;
