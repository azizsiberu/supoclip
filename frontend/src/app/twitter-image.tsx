import { createSocialImageResponse } from "@/lib/social-image";

export const runtime = "edge";

export const alt = "KlipOS — The operating system for vertical automation";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return createSocialImageResponse();
}
