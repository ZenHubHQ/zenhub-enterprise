#!/bin/bash

# Copy/create required template files
rm base/kraken/configmaps.yaml 2> /dev/null || true
rm zhe-urls.env 2> /dev/null || true
touch zhe-urls.env
rm base/kustomization.yaml 2> /dev/null || true
cp template-files/kraken-configmaps.template base/kraken/configmaps.yaml
cp template-files/base-kustomization.template base/kustomization.yaml

## Exports "configuration" configmap vars to this subshell
export `grep -ir "domain_tld=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "subdomain_suffix=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "admin_ui_subdomain=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "github_hostname=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "chrome_extension_webstore_url=" kustomization.yaml | awk '{print $3}'`
export `grep -ir "graphiql_explorer_subdomain_prefix=" kustomization.yaml | awk '{print $3}'`

zhe_hostname="$subdomain_suffix.$domain_tld"
https_zhe_hostname="https://$zhe_hostname"
admin_zhe_hostname="$admin_ui_subdomain.$domain_tld"
devsite_zhe_hostname="$graphiql_explorer_subdomain_prefix-$zhe_hostname"
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
