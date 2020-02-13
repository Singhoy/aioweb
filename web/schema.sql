# 运行mysql -u root -p < schema.sql
drop database if exists aioweb;

create database aioweb;

use aioweb;

create user 'www'@'localhost' identified by '123';
grant select, insert, update, delete on aioweb.* to 'www'@'localhost';
flush privileges;

create table users
(
  `id`         varchar(50)  not null,
  `email`      varchar(50)  not null,
  `pwd`        varchar(50)  not null,
  `admin`      bool         not null,
  `name`       varchar(50)  not null,
  `image`      varchar(500) not null,
  `created_at` real         not null,
  unique key `idx_email` (`email`),
  key `idx_created_at` (`created_at`),
  primary key (`id`)
) engine = innodb
  default charset = utf8;

create table blogs
(
  `id`         varchar(50)  not null,
  `user_id`    varchar(50)  not null,
  `user_name`  varchar(50)  not null,
  `user_image` varchar(500) not null,
  `name`       varchar(50)  not null,
  `summary`    varchar(200) not null,
  `content`    mediumtext   not null,
  `created_at` real         not null,
  key `idx_created_at` (`created_at`),
  primary key (`id`)
) engine = innodb
  default charset = utf8;

create table comments
(
  `id`         varchar(50)  not null,
  `blog_id`    varchar(50)  not null,
  `user_id`    varchar(50)  not null,
  `user_name`  varchar(50)  not null,
  `user_image` varchar(500) not null,
  `content`    mediumtext   not null,
  `created_at` real         not null,
  key `idx_created_at` (`created_at`),
  primary key (`id`)
) engine = innodb
  default charset = utf8;
