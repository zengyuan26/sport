declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    INTERNAL_ACCESS_CODE?: string;
    CREATION_GPT_URL?: string;
  }
}
