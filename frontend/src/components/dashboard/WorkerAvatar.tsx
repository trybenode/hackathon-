import Image from "next/image";

/** Initials stand in until workers have avatars. */
function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** A worker's photo, or their initials, in a circle. */
export function WorkerAvatar({
  name,
  src,
  size = 44,
}: {
  name: string;
  src: string | null;
  size?: number;
}) {
  return (
    <span
      className="flex shrink-0 items-center justify-center overflow-hidden rounded-pill bg-badge-high text-body-sm font-semibold text-grey-900"
      style={{ width: size, height: size }}
    >
      {src ? (
        <Image src={src} alt="" width={size} height={size} unoptimized className="h-full w-full object-cover" />
      ) : (
        initialsOf(name)
      )}
    </span>
  );
}
