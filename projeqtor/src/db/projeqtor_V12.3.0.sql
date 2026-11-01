-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.3.0                                      //
-- // Date : 2025-06-25                                     //
-- ///////////////////////////////////////////////////////////

-- to add notes on closed or readonly items
INSERT INTO `${prefix}habilitationother` (idProfile, scope, rightAccess)
SELECT id, 'canAddNoteClosedEl', '2' FROM `${prefix}profile`;

INSERT INTO `${prefix}habilitationother` (idProfile, scope, rightAccess)
SELECT id, 'canAddNoteReadOnlyEl', '2' FROM `${prefix}profile`;

INSERT INTO `${prefix}habilitationother` (idProfile, scope, rightAccess)
SELECT id, 'enableAutomaticCal', '1' FROM `${prefix}profile` WHERE id=1 OR  id=3;

INSERT INTO `${prefix}habilitationother` (idProfile, scope, rightAccess)
SELECT id, 'enableAutomaticCal', '2' FROM `${prefix}profile` WHERE id!=1 AND  id!=3;

-- to insert menuResourceSkillSimple in menu
INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(316, 'menuResourceSkillSimple', 208, 'item', 445, null, 0, 'Skill',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`) VALUES
(413, 'menuResourceSkillSimple',112,316,0,66);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 316, 1),
(2, 316, 1),
(3, 316, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 316, 8),
(2, 316, 8),
(3, 316, 7);

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(246,32,316,0,1);

-- allow from unknown users and keep trace of emails
ALTER TABLE `${prefix}inputmailboxticket` ADD COLUMN `addPseudoUsers` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}resource` ADD COLUMN `dummy` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}subscription` ADD COLUMN `inCopy` int(1) unsigned DEFAULT '0' COMMENT '1';

-- Favorite project list 
ALTER TABLE `${prefix}filter` ADD `isFavoriteProject` int(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}favoriteprojectlist` ADD `idFilter` int(12) unsigned DEFAULT NULL COMMENT '12';

-- automatic email when a skill expires
INSERT INTO `${prefix}cronexecution` (`cron`, `fileExecuted`, `idle`, `fonctionName`, `nextTime`) VALUES 
('30 1 * * *', '../tool/cronExecutionStandard.php', '1', 'cronSkillsAlertCron', NULL);
INSERT INTO `${prefix}parameter` (idUser,idProject, parameterCode, parameterValue) VALUES 
(null, null, 'skillsAlertResource', 'NO'),
(null, null, 'skillsAlertTeamManager', 'NO'),
(null, null, 'skillsAlertOrganismManager', 'NO'),
(null, null, 'skillsAlertLeadTimes', '0'),
(null, null, 'skillsAlertPeriodicity', 'onlyOnce');
ALTER TABLE `${prefix}resourceskill` ADD COLUMN `lastAlertDate` date DEFAULT NULL;

-- QuickPlanning
ALTER TABLE `${prefix}planningelement` ADD COLUMN `quickplanStartDate` date DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `quickplanEndDate` date DEFAULT NULL;
ALTER TABLE `${prefix}planningelement` ADD COLUMN `quickplanUpdated` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}planningelement` ADD COLUMN `assignedDuration` int(5) unsigned DEFAULT null COMMENT '5';
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `quickplanStartDate` date DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `quickplanEndDate` date DEFAULT NULL;
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `assignedDuration` int(5) unsigned DEFAULT null COMMENT '5';
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `quickplanUpdated` int(1) unsigned DEFAULT 0 COMMENT '1';

--oAuth2
CREATE TABLE `${prefix}oauthclient` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(200) DEFAULT NULL,
  `idUser` int(12) unsigned COMMENT '12',
  `oauthSource` varchar(200) DEFAULT NULL,
  `tenantId` varchar(200) DEFAULT NULL,
  `clientId` varchar(200) DEFAULT NULL,
  `clientSecret` varchar(2000) DEFAULT NULL,
  `scope` varchar(2000) DEFAULT NULL,
  `token` varchar(4000) DEFAULT NULL,
  `refreshToken` varchar(4000) DEFAULT NULL,
  `tokenDateTime` dateTime DEFAULT NULL,
  `tokenExpires` int(10) unsigned COMMENT '10',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}inputmailboxticket` ADD COLUMN `idOAuthClient` int(12) unsigned COMMENT '12';
ALTER TABLE `${prefix}inputmailboxticket` ADD COLUMN `connectionMode` varchar(100) default 'basic';
ALTER TABLE `${prefix}inputmailboximport` ADD COLUMN `idOAuthClient` int(12) unsigned COMMENT '12';
ALTER TABLE `${prefix}inputmailboximport` ADD COLUMN `connectionMode` varchar(100) default 'basic';
--ALTER TABLE `${prefix}inputmailboxticket` CHANGE `failedRead` `failedRead` int(3) unsigned DEFAULT '0' COMMENT '3';
--ALTER TABLE `${prefix}inputmailboximport` CHANGE `failedRead` `failedRead` int(3) unsigned DEFAULT '0' COMMENT '3';

--new gestion resource and profile picture and attachmment
ALTER TABLE `${prefix}attachment` ADD COLUMN `isProfilePic` int(12) unsigned DEFAULT 0 COMMENT '12';
UPDATE `${prefix}attachment` SET `isProfilePic` = 1 WHERE `refType` = 'Resource';

--Filter : common filter for all users 
ALTER TABLE `${prefix}filter` ADD COLUMN `isCommon` int(1) unsigned DEFAULT '0' COMMENT '1';

-- Copyable RETEX ->analysis Project
INSERT INTO `${prefix}copyable` (`name`, `idle`, `sortOrder`) VALUES
('LessonLearned', 0, 940),
('Assumption', 0, 941),
('Constraint', 0, 942);