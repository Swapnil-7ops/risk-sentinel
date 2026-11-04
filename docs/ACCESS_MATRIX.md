# Access matrix

Authorization is enforced server-side with `login_required` and `role_required`; hidden UI controls are not the security boundary.

| Area | Action | admin | risk_owner | auditor |
|---|---|---:|---:|---:|
| Assets | view / create / edit / delete | yes / yes / yes / yes | yes / yes / yes / yes | yes / no / no / no |
| Risks | view / create / edit / delete | yes / yes / yes / yes | yes / yes / yes / no | yes / no / no / no |
| Mappings | view / create / edit / delete | yes / yes / yes / no | yes / yes / yes / no | yes / no / no / no |
| Treatment evidence | view / create / edit / delete | yes / yes / yes / no | yes / yes / yes / no | yes / no / no / no |
| Treatment approval | view / create / edit / delete | yes / yes / yes / no | yes / no / no / no | yes / no / no / no |
| Treatment escalation | view / create / edit / delete | yes / yes / yes / no | yes / yes / yes / no | yes / no / no / no |
| Risk acceptance approval | view / create / edit / delete | yes / yes / yes / no | yes / no / no / no | yes / no / no / no |
| Treatment board | view / create / edit / delete | yes / yes / yes / no | yes / yes / yes / no | yes / no / no / no |
| Audit logs | view / create / edit / delete | yes / no / no / no | no / no / no / no | yes / no / no / no |
| Analytics | view / create / edit / delete | yes / yes / no / no | yes / yes / no / no | yes / yes / no / no |
| Bookmarks | view / create / edit / delete | own / own / own / own | own / own / own / own | own / own / own / own |
| Settings | view / create / edit / delete | yes / no / yes / no | no / no / no / no | no / no / no / no |
| Users | view / create / edit / delete | yes / yes / yes / no | no / no / no / no | no / no / no / no |

Bookmark queries always include the authenticated user's identifier, so IDs cannot cross the ownership boundary.

User administration edits are CSRF-protected POST actions. Admins cannot deactivate or demote themselves, and the last active admin cannot be deactivated or demoted. Every role, status, and temporary-password reset action is recorded in the audit trail without recording the generated password.
