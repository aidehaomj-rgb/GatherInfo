import React, { useState, useEffect, useCallback } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";

interface BookmarkButtonProps {
  itemId: string;
  size?: number;
  className?: string;
}

const STORAGE_KEY = "traderadar_bookmarks";

function readBookmarks(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function writeBookmarks(set: Set<string>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}

export const BookmarkButton: React.FC<BookmarkButtonProps> = ({
  itemId,
  size = 18,
  className = "",
}) => {
  const [bookmarked, setBookmarked] = useState<boolean>(false);
  const [animating, setAnimating] = useState<boolean>(false);

  useEffect(() => {
    const bookmarks = readBookmarks();
    setBookmarked(bookmarks.has(itemId));
  }, [itemId]);

  const toggle = useCallback(() => {
    const bookmarks = readBookmarks();
    const next = new Set(bookmarks);
    if (next.has(itemId)) {
      next.delete(itemId);
      setBookmarked(false);
    } else {
      next.add(itemId);
      setBookmarked(true);
      setAnimating(true);
      setTimeout(() => setAnimating(false), 300);
    }
    writeBookmarks(next);
  }, [itemId]);

  return (
    <button
      type="button"
      onClick={toggle}
      title={bookmarked ? "取消收藏" : "收藏"}
      className={[
        "bookmark-btn",
        bookmarked ? "bookmarked" : "",
        animating ? "animate-pop" : "",
        className,
      ].join(" ")}
      aria-pressed={bookmarked}
    >
      {bookmarked ? (
        <BookmarkCheck size={size} />
      ) : (
        <Bookmark size={size} />
      )}
    </button>
  );
};
