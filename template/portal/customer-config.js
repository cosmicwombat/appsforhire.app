// ─────────────────────────────────────────────────────────────
// AppsForHire — Customer Portal Config
// Fill this in for each customer when setting up their portal.
// ─────────────────────────────────────────────────────────────

const CUSTOMER = {
  name:        "{{CLIENT_NAME}}",
  tier:        "{{TIER}}",          // starter | custom | pro
  since:       "{{SINCE_DATE}}",    // e.g. "March 2026"
  support_email: "hello@appsforhire.app",

  // Stripe subscription management link (send customer here to manage billing)
  stripe_portal: "https://billing.stripe.com/p/login/YOUR_PORTAL_LINK",

  // List every app this customer has
  apps: [
    {
      name:        "{{APP_1_NAME}}",
      description: "{{APP_1_DESCRIPTION}}",
      url:         "https://{{CLIENT_SLUG}}.appsforhire.app",
      icon:        "{{APP_1_ICON}}",   // emoji
      status:      "active",           // active | maintenance | coming_soon
      launched:    "{{APP_1_DATE}}",
    },
    // Add more apps here as the customer grows:
    // {
    //   name:        "New App",
    //   description: "Description of the new app",
    //   url:         "https://newapp.appsforhire.app",
    //   icon:        "📦",
    //   status:      "coming_soon",
    //   launched:    "Coming April 2026",
    // },
  ]
};
