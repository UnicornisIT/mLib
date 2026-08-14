export type ArtistBrief = { id: string; name: string };
export type AlbumBrief = {
  id: string;
  title: string;
  album_artist: string;
  year: number | null;
  artwork_id: string | null;
};

export type Track = {
  id: string;
  uuid: string;
  title: string;
  artist: ArtistBrief;
  album: AlbumBrief | null;
  album_artist: string | null;
  genre: string | null;
  year: number | null;
  track_number: number | null;
  disc_number: number | null;
  composer: string | null;
  copyright: string | null;
  comment: string | null;
  duration: number;
  file_size: number;
  format: string;
  codec: string | null;
  bitrate: number | null;
  sample_rate: number | null;
  channels: number | null;
  artwork_id: string | null;
  favorite: boolean;
  needs_attention: boolean;
  metadata_status: "complete" | "incomplete" | "critical" | "reviewed";
  metadata_issues: MetadataIssue[];
  play_count: number;
  last_played_at: string | null;
  date_added: string;
  date_modified: string;
};

export type MetadataIssue = "missing_title" | "unknown_artist" | "missing_album" | "missing_genre" | "missing_year";
export type MetadataAttentionSummary = { total: number };

export type TrackPage = { items: Track[]; page: number; page_size: number; total: number; pages: number };
export type Album = {
  id: string;
  title: string;
  album_artist: string;
  artist: ArtistBrief | null;
  year: number | null;
  genre: string | null;
  artwork_id: string | null;
  track_count: number;
  duration: number;
};
export type AlbumDetail = Album & { tracks: Track[] };
export type AlbumPage = { items: Album[]; page: number; page_size: number; total: number; pages: number };
export type Artist = {
  id: string;
  name: string;
  sort_name: string;
  artwork_id: string | null;
  album_count: number;
  track_count: number;
};
export type ArtistDetail = Artist & { albums: Album[]; tracks: Track[] };
export type ArtistPage = { items: Artist[]; page: number; page_size: number; total: number; pages: number };
export type Genre = { name: string; track_count: number; album_count: number };
export type User = {
  id: string;
  username: string;
  display_name: string | null;
  bio: string | null;
  location: string | null;
  birth_date: string | null;
  avatar_color: string;
  is_admin: boolean;
  created_at: string;
};
export type UserProfileUpdate = {
  display_name: string | null;
  bio: string | null;
  location: string | null;
  birth_date: string | null;
  avatar_color: string;
};
export type PasswordChange = {
  current_password: string;
  new_password: string;
  new_password_confirmation: string;
};
export type AuthStatus = { setup_required: boolean; authenticated: boolean };
export type UploadResult = { filename: string; status: "added" | "duplicate" | "error"; detail: string; track: Track | null };
export type ImportJob = {
  id: string;
  path: string;
  status: string;
  found: number;
  processed: number;
  added: number;
  skipped: number;
  errors: number;
  current_file: string | null;
  error_message: string | null;
};
export type PlaylistItem = { id: string; position: number; track: Track };
export type Playlist = {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  created_at: string;
  updated_at: string;
  track_count: number;
  duration: number;
  items: PlaylistItem[] | null;
};
export type Dashboard = {
  tracks: number;
  albums: number;
  artists: number;
  genres: number;
  duration: number;
  recently_added: Track[];
  recently_played: Track[];
  albums_recent: Album[];
};
export type SearchResult = { tracks: Track[]; albums: Album[]; artists: Artist[] };
export type MovieProgress = {
  position: number;
  duration: number;
  completed: boolean;
  updated_at: string;
};
export type MovieFile = {
  id: string;
  display_title: string;
  season_number: number | null;
  episode_number: number | null;
  episode_title: string | null;
  original_filename: string;
  file_size: number;
  format: string;
  mime_type: string;
  duration: number;
  video_codec: string | null;
  audio_codec: string | null;
  width: number | null;
  height: number | null;
  added_at: string;
  progress: MovieProgress | null;
};
export type SeriesTrackingStatus = "watching" | "planned" | "dropped" | "completed";
export type MovieTrackingStatus = "planned" | "watched";
export type TitleTracking = {
  status: SeriesTrackingStatus | MovieTrackingStatus;
  watched_at: string | null;
};
export type MovieSeasonSummary = {
  season_number: number;
  name: string;
  episode_count: number;
  air_date: string | null;
  poster_url: string | null;
  watched_count: number;
};
export type CreditPerson = {
  tmdb_id: number;
  name: string;
  role: string | null;
  profile_url: string | null;
};
export type MediaTitle = {
  id: string;
  media_type: "movie" | "series";
  title: string;
  original_title: string | null;
  year: number | null;
  overview: string | null;
  poster_url: string | null;
  backdrop_url: string | null;
  genres: string[];
  tmdb_rating: number | null;
  release_status: string | null;
  next_air_date: string | null;
  runtime_minutes: number | null;
  episode_runtime_minutes: number | null;
  total_episodes: number;
  total_seasons: number;
  seasons: MovieSeasonSummary[];
  directors: CreditPerson[];
  cast: CreditPerson[];
  tracking: TitleTracking | null;
  metadata_provider: string | null;
  metadata_synced_at: string | null;
  file_count: number;
  watched_count: number;
  progress_percent: number;
  added_at: string;
};
export type MediaTitleDetail = MediaTitle & { files: MovieFile[] };
export type MovieEpisode = {
  tmdb_episode_id: number | null;
  season_number: number;
  episode_number: number;
  name: string;
  overview: string | null;
  air_date: string | null;
  runtime_minutes: number;
  still_url: string | null;
  watched: boolean;
  watched_at: string | null;
};
export type MovieSeason = {
  season_number: number;
  name: string;
  overview: string | null;
  episodes: MovieEpisode[];
  watched_count: number;
  episode_count: number;
};
export type MediaTitlePage = { items: MediaTitle[]; total: number; page: number; page_size: number; pages: number };
export type TmdbCatalogTitle = {
  tmdb_id: number;
  media_type: "movie" | "series";
  title: string;
  original_title: string | null;
  year: number | null;
  overview: string | null;
  poster_url: string | null;
  backdrop_url: string | null;
  tmdb_rating: number | null;
  local_title_id: string | null;
  file_count: number;
  match_reason: string | null;
};
export type TmdbCatalogPage = {
  items: TmdbCatalogTitle[];
  page: number;
  pages: number;
  total: number;
  configured: boolean;
};
export type PersonFilmography = {
  tmdb_id: number;
  name: string;
  known_for_department: string | null;
  biography: string | null;
  birthday: string | null;
  place_of_birth: string | null;
  profile_url: string | null;
  items: TmdbCatalogTitle[];
};
export type ContinueWatching = { title: MediaTitle; file: MovieFile | null };
export type MovieDashboard = {
  titles: number;
  movies: number;
  series: number;
  episodes: number;
  continue_watching: ContinueWatching[];
  recently_added: MediaTitle[];
};
export type MovieProfileSummary = { episodes: number; movies: number; minutes: number; days: number };
export type MovieProfileActivity = {
  date: string;
  episodes: number;
  movies: number;
  minutes: number;
  episode_minutes: number;
  movie_minutes: number;
};
export type MovieProfile = {
  username: string;
  member_since: string;
  summaries: Record<"all" | "series" | "movies", MovieProfileSummary>;
  activity: MovieProfileActivity[];
  series_status_counts: Record<SeriesTrackingStatus, number>;
  movie_status_counts: Record<MovieTrackingStatus, number>;
  series_titles: Record<SeriesTrackingStatus, MediaTitle[]>;
  movie_titles: Record<MovieTrackingStatus, MediaTitle[]>;
};
export type MovieUpload = {
  id: string;
  filename: string;
  size: number;
  offset: number;
  status: "uploading" | "processing" | "completed" | "error";
  chunk_size: number;
  file_id: string | null;
  title_id: string | null;
  error: string | null;
};
export type AppSettings = {
  library: { library_path: string; import_path: string; supported_extensions: string[] };
  metadata: {
    embedded_metadata: boolean;
    musicbrainz_enabled: boolean;
    cover_art_archive_enabled: boolean;
    auto_artwork: boolean;
  };
  playback: { save_volume: boolean; autoplay: boolean; default_repeat: "off" | "all" | "one" };
  appearance: { theme: "dark" | "light" | "system" };
  system: { version: string; ffmpeg_available: boolean; database: string; library_size: number };
};
export type MovieSettings = {
  tmdb_enabled: boolean;
  metadata_refresh_hours: number;
  storage_path: string;
  library_size: number;
  database: string;
};

export type Book = {
  id: string;
  media_type: "ebook" | "audiobook";
  title: string;
  author: string;
  description: string | null;
  genre: string | null;
  language: string | null;
  publication_year: number | null;
  publisher: string | null;
  isbn: string | null;
  narrator: string | null;
  page_count: number | null;
  duration: number | null;
  original_filename: string;
  file_size: number;
  format: string;
  mime_type: string;
  has_cover: boolean;
  added_at: string;
  updated_at: string;
};

export type BookPage = { items: Book[]; total: number };
export type BooksDashboard = {
  total: number;
  ebooks: number;
  audiobooks: number;
  authors: number;
  storage_bytes: number;
};

export type CollectionFieldType = "text" | "long_text" | "number" | "date" | "checkbox" | "select" | "url" | "price" | "rating";
export type CollectionFieldValue = string | number | boolean | null;
export type CollectionField = {
  id: string;
  name: string;
  field_type: CollectionFieldType;
  position: number;
  required: boolean;
  show_on_card: boolean;
  options: string[];
};
export type CollectCollection = {
  id: string;
  name: string;
  description: string | null;
  color: string;
  item_count: number;
  photo_count: number;
  fields: CollectionField[];
  created_at: string;
  updated_at: string;
};
export type CollectionTag = { id: string; name: string; color: string };
export type CollectionPhoto = {
  id: string;
  original_filename: string;
  position: number;
  is_cover: boolean;
  created_at: string;
};
export type CollectionItem = {
  id: string;
  collection_id: string;
  collection_name: string;
  name: string;
  description: string | null;
  quantity: number;
  location: string | null;
  photos: CollectionPhoto[];
  tags: CollectionTag[];
  custom_values: Record<string, CollectionFieldValue>;
  created_at: string;
  updated_at: string;
};
export type CollectionItemPage = { items: CollectionItem[]; total: number; locations: string[] };
export type CollectionsDashboard = { collections: number; items: number; photos: number; locations: number };

export type GameStatus = "not_started" | "playing" | "completed" | "completed_100" | "abandoned";
export type GamePlatform = "PC" | "PlayStation" | "Xbox" | "Switch" | "Retro";
export type Game = {
  id: string;
  title: string;
  developer: string | null;
  publisher: string | null;
  release_year: number | null;
  genre: string | null;
  platform: GamePlatform;
  purchase_date: string | null;
  acquired_from: string | null;
  status: GameStatus;
  playtime_minutes: number;
  personal_rating: number | null;
  achievements_unlocked: number;
  achievements_total: number;
  cover_url: string | null;
  screenshots: string[];
  created_at: string;
  updated_at: string;
};
export type GamePage = { items: Game[]; total: number };
export type GamesDashboard = {
  total: number;
  playing: number;
  completed: number;
  completed_100: number;
  playtime_minutes: number;
  achievements_unlocked: number;
  achievements_total: number;
};

export type WishCategory = "watch" | "read" | "listen" | "buy";
export type WishTargetType = "movie" | "series" | "book" | "album" | "game" | "item" | "other";
export type WishStatus = "active" | "fulfilled";
export type Wish = {
  id: string;
  category: WishCategory;
  target_type: WishTargetType;
  title: string;
  creator: string | null;
  notes: string | null;
  reference_url: string | null;
  image_url: string | null;
  status: WishStatus;
  matched_service: string | null;
  matched_item_id: string | null;
  auto_fulfilled: boolean;
  created_at: string;
  updated_at: string;
  fulfilled_at: string | null;
};
export type WishPage = { items: Wish[]; total: number };
export type WishesDashboard = {
  total: number;
  active: number;
  fulfilled: number;
  auto_fulfilled: number;
  by_category: Record<WishCategory, number>;
};
