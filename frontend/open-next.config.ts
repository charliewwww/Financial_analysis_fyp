import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Default configuration: no persistent incremental cache override.
// If you later want Next.js ISR/data caching backed by Cloudflare R2, create an
// R2 bucket bound as NEXT_INC_CACHE_R2_BUCKET and pass r2IncrementalCache here.
// See https://opennext.js.org/cloudflare/caching
export default defineCloudflareConfig();
