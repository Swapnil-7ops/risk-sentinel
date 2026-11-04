# Limitations

- Public audit log growth is not automatically archived or purged.
- MFA is currently required for administrators and risk owners; auditors do not require MFA.
- Email verification and password reset require correctly configured SMTP credentials.
- The database is single-region.
- Application fields are not independently encrypted at rest beyond the encryption Atlas provides.
