export interface CurrentUser {
  username: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: "bearer";
}
