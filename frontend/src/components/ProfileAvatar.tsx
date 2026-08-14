import type { User } from "@/lib/types";

export function userDisplayName(user: User | null | undefined) {
  return user?.display_name || user?.username || "Профиль";
}

export function ProfileAvatar({
  user,
  className = "avatar",
}: {
  user: User | null | undefined;
  className?: string;
}) {
  const name = userDisplayName(user);
  return (
    <span
      className={className}
      style={{ backgroundColor: user?.avatar_color || undefined }}
      aria-hidden="true"
    >
      {name.slice(0, 1).toUpperCase() || "—"}
    </span>
  );
}
