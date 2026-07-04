/**
 * Admin helper.
 *
 * Operator status is decided by the SERVER: the `role` field on the
 * authenticated user's profile (`/users/me`), enforced by the backend's
 * `require_admin` dependency on every operator endpoint. The browser never
 * decides authorization — this helper only toggles the visibility of
 * operator-only UI. A user who forces the UI open still cannot call admin
 * endpoints, because the server re-checks the role on every request.
 */
export function isAdminRole(role: string | null | undefined): boolean {
  return role === "admin";
}
