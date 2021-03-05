window.config = {
  ZENHUB_SERVER_ADDRESS: "https://$(subdomain_suffix).$(domain_tld)/api",
  ZENHUB_WEBAPP_ADDRESS: "https://$(subdomain_suffix).$(domain_tld)",
  hostURL: "https://$(subdomain_suffix).$(domain_tld)/api",
  loginURL: "https://$(subdomain_suffix).$(domain_tld)/api/auth/github",
  dashboardURL: "https://$(subdomain_suffix).$(domain_tld)/dashboard",
  webappURL: "https://$(subdomain_suffix).$(domain_tld)",
  GITHUB_SERVER_ADDRESS: "$(github_hostname)",
  githubURL: "$(github_hostname)",
  githubRestApiUrl: "$(github_hostname)/api/v3",
  githubGraphQLApiUrl: "$(github_hostname)/api/graphql",
  marketplaceURL: "",
  CAMO: "",
  CAMO_HOST: "",
  companyDomain: "ZenHub",
  ENV: "enterprise",
  env: "enterprise",
  isEnterprise: true,
  isDev: false,
  mixpanel: "",
  rollbar: "",
  salesmachine: "",
  stripe: "",
  isLicenseGovernanceEnabled: false,
  maxFileUpload: 15728640,
  maxFileUploadString: "15 MB",
  repoFetchPageLimit: 12,
  isUploadFileToLocal: false,
  isTrackerEnabled: false,
  verboseLogs: false,
  NO_CHECK_UPDATE_FOR_OPENED_ISSUE_VIEWER: true,
  ZENHUB_CHROME_EXT_WEBSTORE_URL: "$(chrome_extension_webstore_url)",
  ZENHUB_FIREFOX_EXT_JSON_URL: "https://$(subdomain_suffix).$(domain_tld)/zhe-public/ff-ext-signed/latest.json",
  ZENHUB_FIREFOX_EXT_XPI_ROOT_URL: "https://$(subdomain_suffix).$(domain_tld)/zhe-public/ff-ext-signed",
};