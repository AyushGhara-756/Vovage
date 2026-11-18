export const AVATAR_MAX_BYTES = 2 * 1024 * 1024;

const AVATAR_TYPES: Record<string, string> = {
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  webp: "image/webp",
  gif: "image/gif",
};

export function validateAvatarFile(file: {
  name: string;
  type: string;
  size: number;
}): string {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const expected = AVATAR_TYPES[extension];
  if (!expected) {
    throw new Error("Choose a PNG, JPEG, WebP, or GIF image.");
  }

  const declared = (file.type || "").split(";")[0].trim().toLowerCase();
  if (!declared) {
    throw new Error("That file type could not be verified — try another image.");
  }
  if (declared !== expected) {
    throw new Error("File extension and image type must match.");
  }
  if (file.size <= 0) throw new Error("That file is empty.");
  if (file.size > AVATAR_MAX_BYTES) throw new Error("Avatar must be under 2 MB.");
  return declared;
}
