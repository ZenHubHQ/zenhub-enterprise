# Deploy Zenhub Sample

Deploy everything as containers, which an Ingress expecting an Nginx Ingress configured in the Cluster. 


* Build the manifests
```bash
go run build_zhe_vanilla.go
```
* Zenhub Enterprise 3.0.0 (running code from Zenhub Enterprise 2.44 - aka pre-Sauron)
```bash
zenhub_base=enterprise/public_repo/sample/3.0
```
* Zenhub Enterprise 3.0.0 (running lastest code from Zenhub - aka master)
```bash
zenhub_base=enterprise/public_repo/sample/3.2
```
* deploy all
```bash
kustomize build --load_restrictor=none ${zenhub_base}/mocked_database | kubectl apply -f -
kustomize build --load_restrictor=none ${zenhub_base}/mocked_ingress | kubectl apply -f -
kustomize build --load_restrictor=none ${zenhub_base} | kubectl apply -f -
```

> expect zhe30 or zhe32 namespace to already exist
