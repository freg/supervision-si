-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 13.0.0                                      //
-- // Date : 2025-04-01                                     //
-- ///////////////////////////////////////////////////////////


-- Abacus
CREATE TABLE `${prefix}phase` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idPhasing` int(12) DEFAULT NULL COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `duration` int(5) DEFAULT NULL COMMENT '5',
  `shortName` varchar(15) DEFAULT NULL,
  `sortOrder` int(5) DEFAULT NULL COMMENT '5',
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_phase_phasing` ON `${prefix}phase` (`idPhasing`);

CREATE TABLE `${prefix}abacusvalue` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idAbacusDefinition` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAbacusLine` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idPhase` int(12) unsigned DEFAULT NULL COMMENT '12',
  `value` decimal(9,2) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_abacusvalue_phase` ON `${prefix}abacusvalue` (`idPhase`);
CREATE INDEX `idx_abacusvalue_abacusdef` ON `${prefix}abacusvalue` (`idAbacusDefinition`);
CREATE INDEX `idx_abacusvalue_abacusLine` ON `${prefix}abacusvalue` (`idAbacusLine`);

ALTER TABLE `${prefix}abacusable` ADD `inputField` INT(1) DEFAULT 0;

ALTER TABLE `${prefix}abacusdefinition` ADD `idAbacusable1` int(12) DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}abacusdefinition` ADD `idAbacusable2` int(12) DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}abacusdefinition` ADD `idAbacusable3` int(12) DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}abacusdefinition` ADD `idAbacusable4` int(12) DEFAULT NULL COMMENT '12';
ALTER TABLE `${prefix}abacusdefinition` ADD `idAbacusable5` int(12) DEFAULT NULL COMMENT '12';

-- className1 to className5
UPDATE `${prefix}abacusdefinition` ad SET idAbacusable1 = (SELECT ab.id FROM `${prefix}abacusable` ab WHERE ab.className = ad.className1) WHERE ad.className1 IS NOT NULL AND ad.className1 <> '';
UPDATE `${prefix}abacusdefinition` ad SET idAbacusable2 = (SELECT ab.id FROM `${prefix}abacusable` ab WHERE ab.className = ad.className2) WHERE ad.className1 IS NOT NULL AND ad.className2 <> '';
UPDATE `${prefix}abacusdefinition` ad SET idAbacusable3 = (SELECT ab.id FROM `${prefix}abacusable` ab WHERE ab.className = ad.className3) WHERE ad.className1 IS NOT NULL AND ad.className3 <> '';
UPDATE `${prefix}abacusdefinition` ad SET idAbacusable4 = (SELECT ab.id FROM `${prefix}abacusable` ab WHERE ab.className = ad.className4) WHERE ad.className1 IS NOT NULL AND ad.className4 <> '';
UPDATE `${prefix}abacusdefinition` ad SET idAbacusable5 = (SELECT ab.id FROM `${prefix}abacusable` ab WHERE ab.className = ad.className5) WHERE ad.className1 IS NOT NULL AND ad.className5 <> '';

ALTER TABLE `${prefix}abacusdefinition` ADD `assignmentWorkType` VARCHAR(20) DEFAULT 'fixed';

ALTER TABLE `${prefix}project` ADD `idPhasing` int(12) DEFAULT NULL COMMENT '12';
CREATE INDEX `idx_project_phasing` ON `${prefix}project` (`idPhasing`);

ALTER TABLE `${prefix}activity` ADD `idPhase` int(12) DEFAULT NULL COMMENT '12';
CREATE INDEX `idx_activity_phase` ON `${prefix}activity` (`idPhase`);

CREATE TABLE `${prefix}abacusprojectassignment` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idAbacusProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAssignment` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAbacusDefinition` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAffectable` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12) unsigned DEFAULT NULL COMMENT '12',
  `value` decimal(7,2) DEFAULT NULL,
   PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_abacusprojectassignment_abacusdef` ON `${prefix}abacusprojectassignment` (`idAbacusDefinition`);
CREATE INDEX `idx_abacusprojectassignment_project` ON `${prefix}abacusprojectassignment` (`idProject`);
CREATE INDEX `idx_abacusprojectassignment_ref` ON `${prefix}abacusprojectassignment` (`refType`, `refId`);

-- MAJ v12.5 → v13.0 — menu 331
UPDATE `${prefix}accessright` SET `idAccessProfile` = 1000001 WHERE `idMenu` = 331 AND `idProfile` = 1;
UPDATE `${prefix}accessright` SET `idAccessProfile` = 1000002 WHERE `idMenu` = 331 AND `idProfile` != 1;
UPDATE `${prefix}menu` SET `level` = 'ReadWritePrincipal' WHERE `id` = 331;
UPDATE `${prefix}menu` SET `menuClass` = 'EnvironmentalParameter' WHERE `id` = 331;

-- MAJ v12.5 → v13.0 — menu 332
UPDATE `${prefix}accessright` SET `idAccessProfile` = 1000001 WHERE `idMenu` = 332 AND `idProfile` = 1;
UPDATE `${prefix}accessright` SET `idAccessProfile` = 1000002 WHERE `idMenu` = 332 AND `idProfile` != 1;
UPDATE `${prefix}menu` SET `level` = 'ReadWritePrincipal' WHERE `id` = 332;
UPDATE `${prefix}menu` SET `menuClass` = 'EnvironmentalParameter' WHERE `id` = 331;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(333,'menuAbacusPhase', 6, 'item', 1898, 'ReadWritePrincipal', 0, 'EnvironmentalParameter');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`, `moduleName`) VALUES
(433, 'menuAbacusPhase',430,333,0,40,'moduleAbacus');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 333, 1),
(2, 333, 1),
(3, 333, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 333, 1000001);
INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) 
SELECT `id`, 333, 1000002 FROM `${prefix}profile` WHERE `id`!=1;

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(261,38,333,0,0);

ALTER TABLE `${prefix}abacusproject` ADD `capacity` decimal(5,2) UNSIGNED DEFAULT NULL;

-- hatchPattern
ALTER TABLE `${prefix}planningelement` ADD COLUMN `hatchPattern` varchar(20) DEFAULT NULL;
ALTER TABLE `${prefix}type` ADD COLUMN `hatchPattern` varchar(20) DEFAULT NULL;

UPDATE `${prefix}health` set icon='modernWeatherSun.png' WHERE icon='weatherSun.png';
UPDATE `${prefix}health` set icon='modernWeatherCloud.png' WHERE icon='weatherCloud.png';
UPDATE `${prefix}health` set icon='modernWeatherRain.png' WHERE icon='weatherDanger.png';
UPDATE `${prefix}health` set icon='modernWeatherThunder.png' WHERE icon='weatherStorm.png';
UPDATE `${prefix}health` set icon='modernPause.png' WHERE icon is null and color='#E0E0E0';
UPDATE `${prefix}trend` SET icon='modernTrendUp.png' WHERE icon='arrowUpGreen.png';
UPDATE `${prefix}trend` SET icon='modernTrendEven.png' WHERE icon='arrowRightGrey.png';
UPDATE `${prefix}trend` SET icon='modernTrendDown.png' WHERE icon='arrowDownRed.png';
UPDATE `${prefix}quality` SET icon='modernControlOK.png' WHERE icon='smileyGreen.png';
UPDATE `${prefix}quality` SET icon='modernControlRemarks.png' WHERE icon='smileyYellow.png';
UPDATE `${prefix}quality` SET icon='modernControlKO.png' WHERE icon='smileyRed.png';


-- add user and creation time on Todo list
ALTER TABLE `${prefix}subtask` ADD `creationDateTime` datetime DEFAULT NULL;
ALTER TABLE `${prefix}subtask` ADD `idUser` int(12) unsigned DEFAULT NULL COMMENT '12';

CREATE INDEX subTaskUser ON `${prefix}subtask` (`idUser`);

ALTER TABLE `${prefix}userstory` ADD `acceptationCriteria` mediumtext DEFAULT NULL;

-- #11532 - Allow notifications on Agile items
INSERT INTO `${prefix}notifiable` (`notifiableitem`, `name`, `idle`) VALUES 
('UserStory', 'UserStory', 0),
('Sprint', 'Sprint', 0),
('Epic', 'Epic', 0);

INSERT INTO `${prefix}mailable` (`name`, `idle`) VALUES 
('UserStory', 0),
('Sprint', 0),
('Epic', 0);

-- "See all absences" right on the leaves dashboard habilitation
ALTER TABLE `${prefix}leavessystemhabilitation` ADD `seeAllAccess` VARCHAR(10) DEFAULT NULL;

-- 1. New Report Category "Agile"
INSERT INTO `${prefix}reportcategory` (`id`, `name`, `sortOrder`, `idle`)
VALUES (30, 'reportCategoryAgile', 35, 0);

-- 2. New Report User Stories Burndown
INSERT INTO `${prefix}report`
  (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `idle`, `orientation`,
   `hasCsv`, `hasView`, `hasPrint`, `hasPdf`, `hasToday`, `hasFavorite`,
   `hasWord`, `hasExcel`, `filterClass`, `referTo`)
VALUES
  (147, 'reportUserStoriesBurndownChart', 30, 'userStoriesBurndown.php', 400, 0, 'L',
   0, 1, 1, 1, 1, 1, 0, 0, 'UserStory', NULL);

INSERT INTO `${prefix}reportparameter`
  (`idReport`, `name`, `paramType`, `sortOrder`, `idle`,
   `defaultValue`, `multiple`, `required`)
VALUES
  (147, 'idProject', 'projectList', 10, 0, 'currentProject', 0, 1),
  (147, 'idSprint',  'sprintList',  20, 0, NULL,             0, 0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`)
SELECT id, 147, 1 FROM `${prefix}profile`;

INSERT INTO `${prefix}modulereport` (`idModule`, `idReport`, `hidden`, `active`)
VALUES (37, 147, 0, 1);