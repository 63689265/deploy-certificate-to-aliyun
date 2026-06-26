import datetime
import os
from aliyunsdkcore.client import AcsClient
from aliyunsdkcdn.request.v20180510 import SetCdnDomainSSLCertificateRequest

def get_env_var(key):
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Environment variable {key} not set")
    return value

def file_exists_and_not_empty(file_path):
    expanded_path = os.path.expanduser(file_path)
    return os.path.isfile(expanded_path) and os.path.getsize(expanded_path) > 0

def upload_certificate(client, domain_name, cert_path, key_path):
    expanded_cert_path = os.path.expanduser(cert_path)
    expanded_key_path = os.path.expanduser(key_path)

    if not file_exists_and_not_empty(expanded_cert_path) or not file_exists_and_not_empty(expanded_key_path):
        raise FileNotFoundError(f"Certificate or key file for domain {domain_name} is missing or empty")
    
    with open(expanded_cert_path, 'r') as f:
        cert = f.read()

    with open(expanded_key_path, 'r') as f:
        key = f.read()

    request = SetCdnDomainSSLCertificateRequest.SetCdnDomainSSLCertificateRequest()
    # CDN加速域名
    request.set_DomainName(domain_name)
    # 证书名称
    request.set_CertName(domain_name + datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    request.set_CertType('upload')
    request.set_SSLProtocol('on')
    request.set_SSLPub(cert)
    request.set_SSLPri(key)
    request.set_CertRegion('cn-hangzhou')

    response = client.do_action_with_exception(request)
    # 仅输出成功状态，避免将完整 API 响应（含证书 ID 等元数据）泄露到日志
    print(f"Certificate uploaded successfully for CDN domain: {domain_name}")

def main():
    access_key_id = get_env_var('ALIYUN_ACCESS_KEY_ID')
    access_key_secret = get_env_var('ALIYUN_ACCESS_KEY_SECRET')
    domains = [d.strip() for d in get_env_var('DOMAINS').split(',')]
    cdn_domains = [d.strip() for d in get_env_var('ALIYUN_CDN_DOMAINS').split(',')]

    # 支持两种模式：
    # 1. 1个主域名 + N个CDN域名 → 同一张泛域名证书部署到所有CDN域名
    # 2. N个主域名 + N个CDN域名 → 一一对应部署
    if len(domains) == 1:
        # 单域名模式：同一张证书部署到所有 CDN 域名
        domain = domains[0]
        pairing = [(domain, cdn) for cdn in cdn_domains]
    elif len(domains) == len(cdn_domains):
        pairing = list(zip(domains, cdn_domains))
    else:
        raise ValueError(
            f"DOMAINS count ({len(domains)}) must be 1 (shared cert) "
            f"or match ALIYUN_CDN_DOMAINS count ({len(cdn_domains)})"
        )

    client = AcsClient(access_key_id, access_key_secret, 'cn-hangzhou')
    failed = []

    for domain, cdn_domain in pairing:
        cert_path = f'~/certs/{domain}/fullchain.pem'
        key_path = f'~/certs/{domain}/privkey.pem'
        try:
            upload_certificate(client, cdn_domain, cert_path, key_path)
        except Exception as e:
            print(f"[ERROR] Failed to upload cert for {cdn_domain}: {e}")
            failed.append(cdn_domain)

    if failed:
        raise RuntimeError(f"Upload failed for {len(failed)} domain(s): {', '.join(failed)}")

if __name__ == "__main__":
    main()