CREATE TABLE shows (
    uid  VARCHAR(8)   NOT NULL,
    name VARCHAR(255) NOT NULL,
    PRIMARY KEY (uid)
);

CREATE TABLE seasons (
    uid      VARCHAR(8)   NOT NULL,
    show_uid VARCHAR(8)   NOT NULL,
    number   INT          NOT NULL,
    title    VARCHAR(255),
    is_complete TINYINT(1)   DEFAULT NULL,
    PRIMARY KEY (uid),
    UNIQUE  KEY uq_season (show_uid, number),
    FOREIGN KEY (show_uid) REFERENCES shows(uid)
);

CREATE TABLE episodes (
    uid           VARCHAR(8)   NOT NULL,
    season_uid    VARCHAR(8)   NOT NULL,
    number        INT          NOT NULL,
    title         VARCHAR(255),
    youtube_id    VARCHAR(20),
    published_at  DATETIME,
    thumbnail_url VARCHAR(500),
    PRIMARY KEY (uid),
    UNIQUE  KEY uq_episode (season_uid, number),
    FOREIGN KEY (season_uid) REFERENCES seasons(uid)
);

CREATE TABLE users (
    uid      VARCHAR(8)   NOT NULL,
    email    VARCHAR(255) NOT NULL,
    name            VARCHAR(255)  NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_anonymous    TINYINT(1)   DEFAULT NULL,
    location        VARCHAR(255),
    is_admin        TINYINT(1)   DEFAULT NULL,
    is_test_account TINYINT(1)   DEFAULT NULL,
    wants_more      TINYINT(1)   DEFAULT NULL,
    active          TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (uid),
    UNIQUE KEY uq_email (email)
);

CREATE TABLE user_episodes (
    user_uid    VARCHAR(8) NOT NULL,
    episode_uid VARCHAR(8) NOT NULL,
    is_complete TINYINT(1) DEFAULT NULL,
    PRIMARY KEY (user_uid, episode_uid),
    FOREIGN KEY (user_uid)    REFERENCES users(uid),
    FOREIGN KEY (episode_uid) REFERENCES episodes(uid)
);

CREATE TABLE versions (
    uid            VARCHAR(8)   NOT NULL,
    episode_uid    VARCHAR(8)   NOT NULL,
    version_number INT          NOT NULL,
    filepath       VARCHAR(500) NOT NULL,
    user_uid       VARCHAR(8),
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_merged       TINYINT(1)   DEFAULT NULL,
    PRIMARY KEY (uid),
    UNIQUE  KEY uq_version (episode_uid, user_uid, version_number),
    FOREIGN KEY (episode_uid) REFERENCES episodes(uid),
    FOREIGN KEY (user_uid)    REFERENCES users(uid)
);

CREATE TABLE locations (
    location   VARCHAR(255) NOT NULL,
    season_uid VARCHAR(8)   NOT NULL,
    PRIMARY KEY (location),
    FOREIGN KEY (season_uid) REFERENCES seasons(uid)
);

CREATE TABLE speaker_associations (
    season_uid  VARCHAR(8)   NOT NULL,
    name        VARCHAR(255) NOT NULL,
    order_index INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (season_uid, name),
    KEY idx_speaker_order (season_uid, order_index),
    FOREIGN KEY (season_uid) REFERENCES seasons(uid)
);
