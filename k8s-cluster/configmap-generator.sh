#!/bin/bash

## Exports "configuration" configmap vars to this subshell
export `grep -ir "domain_tld=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "subdomain_suffix=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "admin_ui_subdomain=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "github_hostname=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "chrome_extension_webstore_url=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "graphiql_explorer_subdomain=" kustomization.yaml | awk '{print $3}'`

zhe_hostname="$subdomain_suffix.$domain_tld"
https_zhe_hostname="https://$zhe_hostname"
admin_zhe_hostname="$admin_ui_subdomain.$domain_tld"
devsite_zhe_hostname="$graphiql_explorer_subdomain.$zhe_hostname"
https_admin_zhe_hostname="https://$admin_zhe_hostname"
cable_allowed_origins="$https_zhe_hostname, $github_hostname, null"

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
sed_wrap "s/%%github_hostname%%/$(echo $github_hostname | sed 's_\/_\\/_g')/g" base/kraken/configmaps.yaml
sed_wrap "s/%%chrome_extension_webstore_url%%/$(echo $chrome_extension_webstore_url | sed 's_\/_\\/_g')/g" base/kraken/configmaps.yaml

# Replace malformed double quotes
sed_wrap 's/""""/""/g' base/kraken/configmaps.yaml

# Replace %%___%% in main kustomization.yaml
sed_wrap "s/%%zhe_hostname=%%/zhe_hostname=$zhe_hostname/g" kustomization.yaml
sed_wrap "s/%%https_zhe_hostname=%%/https_zhe_hostname=$(echo $https_zhe_hostname | sed 's_\/_\\/_g')/g" kustomization.yaml
sed_wrap "s/%%admin_zhe_hostname=%%/admin_zhe_hostname=$admin_zhe_hostname/g" kustomization.yaml
sed_wrap "s/%%devsite_zhe_hostname=%%/devsite_zhe_hostname=$devsite_zhe_hostname/g" kustomization.yaml
sed_wrap "s/%%https_admin_zhe_hostname=%%/https_admin_zhe_hostname=$(echo $https_admin_zhe_hostname | sed 's_\/_\\/_g')/g" kustomization.yaml
sed_wrap "s/%%cable_allowed_origins=%%/cable_allowed_origins=$(echo $cable_allowed_origins | sed 's_\/_\\/_g')/g" kustomization.yaml
sed_wrap "s/%%zhe_hostname%%/$zhe_hostname/g" base/kustomization.yaml
