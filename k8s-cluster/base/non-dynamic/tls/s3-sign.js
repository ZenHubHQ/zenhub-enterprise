// Signs the gateway's bucket reads with AWS Signature Version 4 so the buckets
// never need to allow unsigned (anonymous) requests.
//
// Each bucket location sets $s3_host (sent as the Host header), $s3_location
// and $s3_key_prefix. Only
// GET of a single object key is ever signed: the signed URI carries no query
// string, so sub-resources such as ?acl or ?list-type cannot be requested
// with the gateway's credentials.

const crypto = require('crypto');

const EMPTY_PAYLOAD_SHA256 = crypto.createHash('sha256').update('').digest('hex');
const SIGNED_HEADERS = 'host;x-amz-content-sha256;x-amz-date';

function uriEncode(segment) {
    return encodeURIComponent(segment).replace(/[!'()*]/g, function (c) {
        return '%' + c.charCodeAt(0).toString(16).toUpperCase();
    });
}

function objectUri(r) {
    const location = r.variables.s3_location;
    if (!location || !r.uri.startsWith(location)) {
        return '';
    }
    const key = (r.variables.s3_key_prefix || '') + r.uri.slice(location.length);
    if (key === '' || key.endsWith('/')) {
        return '';
    }
    try {
        return '/' + key.split('/').map(uriEncode).join('/');
    } catch (e) {
        return '';
    }
}

function amzDate(r) {
    return new Date().toISOString().replace(/[:-]|\.\d{3}/g, '');
}

function contentSha256(r) {
    return EMPTY_PAYLOAD_SHA256;
}

function hmac(key, data) {
    return crypto.createHmac('sha256', key).update(data).digest();
}

function authorization(r) {
    const uri = r.variables.s3_uri;
    if (!uri) {
        return '';
    }

    const accessKeyId = process.env.BUCKET_ACCESS_KEY_ID;
    const secretAccessKey = process.env.BUCKET_SECRET_ACCESS_KEY;
    const region = process.env.BUCKET_REGION;
    if (!accessKeyId || !secretAccessKey || !region) {
        r.error('bucket credentials or region are not set; refusing to proxy bucket read');
        return '';
    }

    // $s3_amz_date is cached for the request, so the x-amz-date header and
    // the signature always use the same timestamp.
    const date = r.variables.s3_amz_date;
    const day = date.slice(0, 8);
    const scope = day + '/' + region + '/s3/aws4_request';

    const canonicalRequest = [
        'GET',
        uri,
        '',
        'host:' + r.variables.s3_host,
        'x-amz-content-sha256:' + EMPTY_PAYLOAD_SHA256,
        'x-amz-date:' + date,
        '',
        SIGNED_HEADERS,
        EMPTY_PAYLOAD_SHA256,
    ].join('\n');

    const stringToSign = [
        'AWS4-HMAC-SHA256',
        date,
        scope,
        crypto.createHash('sha256').update(canonicalRequest).digest('hex'),
    ].join('\n');

    let signingKey = hmac('AWS4' + secretAccessKey, day);
    signingKey = hmac(signingKey, region);
    signingKey = hmac(signingKey, 's3');
    signingKey = hmac(signingKey, 'aws4_request');
    const signature = crypto.createHmac('sha256', signingKey).update(stringToSign).digest('hex');

    return 'AWS4-HMAC-SHA256 Credential=' + accessKeyId + '/' + scope +
        ', SignedHeaders=' + SIGNED_HEADERS + ', Signature=' + signature;
}

export default { objectUri, amzDate, contentSha256, authorization };
