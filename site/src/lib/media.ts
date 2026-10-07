// What Market Hub publishes outside the portal, as the Media page shows it. Kept by hand: a video
// is added here once it is on YouTube (its address is in the-market-hub-media, in the video's
// published.json), with a cover in site/public/media/ drawn by us, so that the page asks nothing
// of YouTube until a visitor presses play.

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
      ],
      shorts: [
        { id: "4LCtdOLN4DI", title: "The hundred-dollar bill that lost half its value in a drawer", length: "0:44", cover: "inflation-short.jpg" },
        { id: "B0TP-VL4Ov4", title: "The lily pad riddle most people get wrong", length: "0:41", cover: "compound-interest-short.jpg" },
        { id: "uQfP60v2Hts", title: "Nobody taught you this in school", length: "0:49", cover: "money-101-trailer-short.jpg" },
      ],
    },
  ] as Playlist[],
  // Playlists that are planned and have no video yet: shown as empty places, with no promise of what or when.
  upcoming: 2,
};

// The accounts whose posts the page will show. Empty until the owner names them.
export const INSTAGRAM = { handle: "" };
export const X = { handle: "" };

export const shortUrl = (id: string) => `https://www.youtube.com/shorts/${id}`;
