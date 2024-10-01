#!/bin/bash

# Copy/create required template files
rm base/kraken/configmaps.yaml 2> /dev/null || true
rm zhe-urls.env 2> /dev/null || true
touch zhe-urls.env
rm base/kustomization.yaml 2> /dev/null || true
cp template-files/kraken-configmaps.template base/kraken/configmaps.yaml
cp template-files/base-kustomization.template base/kustomization.yaml

## Exports "configuration" configmap vars to this subshell
export `grep -hir "domain_tld=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "subdomain_suffix=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "admin_ui_subdomain=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "github_hostname=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "chrome_extension_webstore_url=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "graphiql_explorer_subdomain_prefix=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "email_pw_enabled=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "w3id_enabled=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "entra_id_enabled=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "ldap_enabled=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "saml_enabled=" kustomization.yaml | awk '{print $2}'`
export `grep -hir "notion_enabled=" kustomization.yaml | awk '{print $2}'`

zhe_hostname="$subdomain_suffix.$domain_tld"
https_zhe_hostname="https://$zhe_hostname"
admin_zhe_hostname="$admin_ui_subdomain.$domain_tld"
devsite_zhe_hostname="$graphiql_explorer_subdomain_prefix-$zhe_hostname"
https_admin_zhe_hostname="https://$admin_zhe_hostname"
cable_allowed_origins="$https_zhe_hostname, $github_hostname, null"
auth_options_email_pw=$email_pw_enabled
auth_options_w3id=$w3id_enabled
auth_options_entra_id=$entra_id_enabled
auth_options_ldap=$ldap_enabled
auth_options_saml=$saml_enabled
feat_options_notion=$notion_enabled

function is_gnu_sed(){
  sed --version >/dev/null 2>&1
}

if is_gnu_sed
then
  sed_wrap() {
    /usr/bin/sed -i "$@"
  }
else
  sed_wrap() {
    /usr/bin/sed -i "" "$@"
  }
fi

## Replace placeholder
sed_wrap "s/%%domain_tld%%/$domain_tld/g" base/kraken/configmaps.yaml
sed_wrap "s/%%subdomain_suffix%%/$subdomain_suffix/g" base/kraken/configmaps.yaml
sed_wrap "s/%%devsite_zhe_hostname%%/$devsite_zhe_hostname/g" base/kraken/configmaps.yaml
sed_wrap "s/%%github_hostname%%/$(echo $github_hostname | sed 's_\/_\\/_g')/g" base/kraken/configmaps.yaml
sed_wrap "s/%%chrome_extension_webstore_url%%/$(echo $chrome_extension_webstore_url | sed 's_\/_\\/_g')/g" base/kraken/configmaps.yaml

# Replace malformed double quotes
sed_wrap 's/""""/""/g' base/kraken/configmaps.yaml

# Create zhe-urls.env for merging to "configuration" ConfigMap resource
cat > zhe-urls.env << EOL
zhe_hostname=$zhe_hostname
https_zhe_hostname=$https_zhe_hostname
admin_zhe_hostname=$admin_zhe_hostname
devsite_zhe_hostname=$devsite_zhe_hostname
https_admin_zhe_hostname=$https_admin_zhe_hostname
cable_allowed_origins=$cable_allowed_origins
EOL

# Replace base/kustomization.yaml placeholder for zhe_hostname
sed_wrap "s/%%zhe_hostname%%/$zhe_hostname/g" base/kustomization.yaml

# Replace W3ID value in base/kraken/configmaps.yaml
sed_wrap "s/\"W3ID\": .*,/\"W3ID\": $auth_options_w3id,/g" base/kraken/configmaps.yaml
sed_wrap "s/\"AzureAD\": .*,/\"AzureAD\": $auth_options_entra_id,/g" base/kraken/configmaps.yaml
sed_wrap "s/\"LDAP\": .*,/\"LDAP\": $auth_options_ldap,/g" base/kraken/configmaps.yaml
sed_wrap "s/\"SAML\": .*,/\"SAML\": $auth_options_saml,/g" base/kraken/configmaps.yaml
# IMPORTANT: Zenhub auth is last in the list and does not contain a comma
# Adding a comma will break firefox extension publishing https://github.com/ZenHubHQ/devops/issues/1889
# If adding a new auth type, keep Zenhub at the bottom of the list
sed_wrap "s/\"Zenhub\": .*/\"Zenhub\": $auth_options_email_pw/g" base/kraken/configmaps.yaml

# Replace integration values in base/kraken/configmaps.yaml
sed_wrap "s/\"isNotionIntegrationEnabled\": .*/\"isNotionIntegrationEnabled\": $feat_options_notion,/g" base/kraken/configmaps.yaml