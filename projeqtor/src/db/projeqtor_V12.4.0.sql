-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.4.0                                      //
-- // Date : 2025-10-07                                     //
-- ///////////////////////////////////////////////////////////

-- Provider Payment Term as mailable
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('ProviderTerm', 0);

-- ProjeQtOr Scrum --

-- ===== ProjeQtOr Scrum -- Project type "Agile" ========================
INSERT INTO `${prefix}type` (`scope`,`name`,`code`,`sortOrder`,`idle`,`idWorkflow`) VALUES
('Project','Agile','AGL', 110, 0, 1);

CREATE TABLE `${prefix}userstory` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `reference` varchar(100) DEFAULT NULL,
  `name` varchar(200) DEFAULT NULL,
  `idUserStoryType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idEpic` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idSprint` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idScrumPriority` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idPersonas` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponent` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProduct` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponentVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `creationDate` datetime DEFAULT NULL,
  `lastUpdateDateTime` datetime DEFAULT NULL,
  `featureAction` mediumtext DEFAULT NULL,
  `featureGoal` mediumtext DEFAULT NULL,
  `featureOpposite` mediumtext DEFAULT NULL,
  `description` mediumtext DEFAULT NULL,
  `result` mediumtext DEFAULT NULL,
  `storyPoints` int(6) unsigned DEFAULT NULL COMMENT '6',
  `businessValue` int(6) unsigned DEFAULT NULL COMMENT '6',
  `handled` int(1) unsigned DEFAULT 0 COMMENT '1',
  `handledDate` date DEFAULT NULL,
  `done` int(1) unsigned DEFAULT 0 COMMENT '1',
  `doneDate` date DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT 0 COMMENT '1',
  `idleDate` date DEFAULT NULL,
  `cancelled` int(1) unsigned DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE INDEX `idx_us_prj` ON `${prefix}userstory` (`idProject`);
CREATE INDEX `idx_us_epic` ON `${prefix}userstory` (`idEpic`);
CREATE INDEX `idx_us_sprint` ON `${prefix}userstory` (`idSprint`);
CREATE INDEX `idx_us_status` ON `${prefix}userstory` (`idStatus`);
CREATE INDEX `userstoryReference` ON `${prefix}userstory` (`reference`);

CREATE TABLE `${prefix}personas` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(200) DEFAULT NULL,
  `code` varchar(5) DEFAULT NULL,
  `sortOrder` int(3) DEFAULT NULL  COMMENT '3',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  `context` mediumtext DEFAULT NULL,
  `goalAndBehavior` mediumtext DEFAULT NULL,
  `involvement` mediumtext DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}scrumpriority` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(200) DEFAULT NULL,
  `color` varchar(7) DEFAULT NULL,
  `sortOrder` int(3) DEFAULT NULL  COMMENT '3',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}epic` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `reference` varchar(100) DEFAULT NULL,
  `name` varchar(200) DEFAULT NULL,
  `idEpicType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idSprint` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `description` mediumtext DEFAULT NULL,
  `result` mediumtext DEFAULT NULL,
  `storyPoints` int(6) unsigned DEFAULT NULL COMMENT '6',
  `businessValue` int(6) unsigned DEFAULT NULL COMMENT '6',
  `creationDate` date DEFAULT NULL,
  `lastUpdateDateTime` datetime DEFAULT NULL,
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `handled` int(1) unsigned DEFAULT 0 COMMENT '1',
  `handledDate` date DEFAULT NULL,
  `done` int(1) unsigned DEFAULT 0 COMMENT '1',
  `doneDate` date DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT 0 COMMENT '1',
  `idleDate` date DEFAULT NULL,
  `cancelled` int(1) unsigned DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE INDEX `idx_epic_prj` ON `${prefix}epic` (`idProject`);
CREATE INDEX `epicReference` ON `${prefix}epic` (`reference`);

CREATE TABLE `${prefix}sprint` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `reference` varchar(100) DEFAULT NULL,
  `name` varchar(200) DEFAULT NULL,
  `idSprintType` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
  `description` mediumtext DEFAULT NULL,
  `result` mediumtext DEFAULT NULL,
  `creationDate` date DEFAULT NULL,
  `lastUpdateDateTime` datetime DEFAULT NULL,
  `idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponent` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idProduct` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idComponentVersion` int(12) unsigned DEFAULT NULL COMMENT '12',
  `fixPlanning` int(1) unsigned default 0 COMMENT '1',
  `paused` int(1) unsigned DEFAULT 0 COMMENT '1',
  `handled` int(1) unsigned DEFAULT 0 COMMENT '1',
  `handledDate` date DEFAULT NULL,
  `done` int(1) unsigned DEFAULT 0 COMMENT '1',
  `doneDate` date DEFAULT NULL,
  `idle` int(1) unsigned DEFAULT 0 COMMENT '1',
  `idleDate` date DEFAULT NULL,
  `cancelled` int(1) unsigned DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE INDEX `idx_sprint_prj` ON `${prefix}sprint` (`idProject`);
CREATE INDEX `sprintReference` ON `${prefix}sprint` (`reference`);

-- ===== ProjeQtOr Scrum -- Menus (Project level objects) ================
INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`, `menuClass`, `idle`) VALUES
(317,'menuUserStory', 2, 'object', 131, 'Project', 'Work', 0),
(318,'menuEpic', 2, 'object', 132, 'Project', 'Work', 0),
(319,'menuSprint', 2, 'object', 133, 'Project', 'Work', 0),
(320,'menuPersonas', 36, 'object', 965, 'Project', 'Work', 0),
(321,'menuSprintBacklog', 2, 'item', 134, 'Project', 'Work', 0),
(322,'menuUserStoryType', 79, 'object', 1065, 'ReadWriteType', 'Type', 0),
(323,'menuSprintType', 79, 'object', 1066, 'ReadWriteType', 'Type', 0),
(324,'menuEpicType', 79, 'object', 1067, 'ReadWriteType', 'Type', 0),
(325,'menuProductBacklog', 2, 'item', 135, 'Project', 'Work', 0),
(328,'menuScrumPriority', 2, 'object', 136, 'Project', 'Work', 0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`, `moduleName`) VALUES
(414, 'navAgile',0,0,0,115,null),
(415, 'menuUserStory',414,317,0,10,null),
(416, 'menuEpic',414,318,0,20,null),
(417, 'menuSprint',414,319,0,30,null),
(418, 'menuPersonas',414,320,0,40,null),
(419, 'menuSprintBacklog',414,321,0,50,null),
(420, 'menuUserStoryType', 132,322,0,70,null),
(421, 'menuSprintType', 132,323,0,80,null),
(422, 'menuEpicType', 132,324,0,90,null),
(423, 'menuProductBacklog',414,325,0,60,null),
(424, 'navPoker', 414, 0, 0, 80, 'moduleVoting'),
(425, 'menuPokerSession', 424, 259, 0, 10,null),
(426, 'menuPokerSessionVoting', 424, 260, 0, 20,null),
(429, 'menuScrumPriority', 414, 328, 0, 70,null);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 317, 1),
(2, 317, 1),
(3, 317, 1),
(1, 318, 1),
(2, 318, 1),
(3, 318, 1),
(1, 319, 1),
(2, 319, 1),
(3, 319, 1),
(1, 320, 1),
(2, 320, 1),
(3, 320, 1),
(1, 321, 1),
(2, 321, 1),
(3, 321, 1),
(1, 322, 1),
(2, 322, 0),
(3, 322, 0),
(1, 323, 1),
(2, 323, 0),
(3, 323, 0),
(1, 324, 1),
(2, 324, 0),
(3, 324, 0),
(1, 325, 1),
(2, 325, 0),
(3, 325, 0),
(1, 328, 1),
(2, 328, 0),
(3, 328, 0);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 317, 8),
(2, 317, 8),
(3, 317, 7),
(1, 318, 8),
(2, 318, 8),
(3, 318, 7),
(1, 319, 8),
(2, 319, 8),
(3, 319, 7),
(1, 320, 8),
(2, 320, 8),
(3, 320, 7),
(1, 321, 8),
(2, 321, 8),
(3, 321, 7),
(1, 322, 8),
(2, 322, 8),
(3, 322, 7),
(1, 325, 8),
(2, 325, 8),
(3, 325, 7),
(1, 328, 8),
(2, 328, 8),
(3, 328, 7);

-- ===== ProjeQtOr Scrum -- Module =======================================
INSERT INTO `${prefix}module` (`id`, `name`, `sortOrder`, `idModule`, `idle`, `active`, `parentActive`, `notActiveAlone`) VALUES
(37, 'moduleAgile', 50, NULL, '0', '1', '0', '0');

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(247,37,317,0,1),
(248,37,318,0,1),
(249,37,319,0,1),
(250,37,320,0,1),
(251,37,321,0,1),
(252,37,322,0,1),
(253,37,323,0,1),
(254,37,324,0,1),
(255,37,325,0,1),
(257,37,328,0,1);

UPDATE `${prefix}modulemenu`
SET idModule = (
    SELECT m.id
    FROM `${prefix}module` m
    WHERE m.name = 'moduleAgile'
)
WHERE idMenu IN (
    SELECT me.id
    FROM `${prefix}menu` me
    WHERE me.name IN (
        'menuPokerComplexity',
        'menuPokerSession',
        'menuPokerSessionType',
        'menuPokerSessionVoting'
    )
);

UPDATE `${prefix}module`
SET idModule = (
        SELECT id
        FROM (
            SELECT id
            FROM `${prefix}module`
            WHERE name = 'moduleAgile'
        ) AS tmp
    ),
    sortOrder = 60
WHERE name = 'modulePoker';


INSERT INTO `${prefix}planningmode` (`id`, `applyTo`, `name`, `code`, `sortOrder`, `idle`, `mandatoryStartDate`, `mandatoryEndDate`, `mandatoryDuration`, `defaultDuration`) VALUES
(31, 'Sprint', 'PlanningModeDDUR', 'DDUR', 100, 0 , 0, 0, 1, 10);

ALTER TABLE `${prefix}status` ADD `forAgileScrum` INT(1) UNSIGNED NOT NULL DEFAULT '0' COMMENT '1';

-- CREATE 5 NEW STATUS FOR AGILE
DELETE FROM `${prefix}tempupdate` WHERE 1=1;
INSERT INTO `${prefix}tempupdate` (id,refId) SELECT id,sortOrder from `${prefix}status` where idle=0 order by sortOrder LIMIT 1;
INSERT INTO `${prefix}status`
(`name`,`setDoneStatus`,`setIdleStatus`,`color`,`sortOrder`,`idle`,`setHandledStatus`,`forAgileScrum`)
VALUES
('to do',0 ,0,'#d2691e',(select min(refId)+1 from `${prefix}tempupdate`),0,0,1),
('in progress',0,0,'#32cd32',(select min(refId)+2 from `${prefix}tempupdate`),0,1,1),
('to test',0,0,'#b367fe',(select min(refId)+3 from `${prefix}tempupdate`),0,1,1),
('done',1,0,'#87ceeb',(select min(refId)+4 from `${prefix}tempupdate`),0,1,1),
('closed',1,1,'#c0c0c0',(select max(refId)+5 from `${prefix}tempupdate`),0,1,1);

-- CREATE WORKFLOW FOR AGILE
INSERT INTO `${prefix}workflow` (`name`, `workflowUpdate`, `sortOrder`, `isLeaveWorkflow`) VALUES
('Agile', '[ ]', '0', '0');

-- HIDE NON AGILE STATUS ON AGILE WORKFLOW
INSERT INTO `${prefix}columnselector`
(`scope`, `objectClass`, `idUser`, `field`, `attribute`, `hidden`, `sortOrder`, `name`)
SELECT
  'workflow',
  concat('workflow#', (select max(id) from `${prefix}workflow`)),
  stat.`id`,
  stat.`name`,
  stat.`name`,
  1,
  999,
  concat('workflow#', (select max(id) from `${prefix}workflow`),' status#',stat.`id`)
FROM `${prefix}status` stat
WHERE forAgileScrum!=1 and stat.id!=(select min(id) from `${prefix}tempupdate`);
-- HIDE AGILE STATUS ON NON AGILE WORKFLOW
INSERT INTO `${prefix}columnselector`
(`scope`, `objectClass`, `idUser`, `field`, `attribute`, `hidden`, `sortOrder`, `name`)
SELECT
  'workflow',
  concat('workflow#', wf.id),
  stat.`id`,
  stat.`name`,
  stat.`name`,
  1,
  999,
  concat('workflow#', (select max(id) from `${prefix}workflow`),' status#',stat.`id`)
FROM `${prefix}status` stat, `${prefix}workflow` wf
WHERE forAgileScrum=1 and wf.id!=(select max(id) from `${prefix}workflow`) ;

-- DEFINE TRANSITION RULES IN WORFLOW AGILE
INSERT INTO `${prefix}workflowstatus`
(`idWorkflow`, `idStatusFrom`, `idStatusTo`, `idProfile`, `allowed`)
SELECT (select max(id) from `${prefix}workflow`), statFrom.id, statTo.id, prof.id, 1
FROM `${prefix}status` statFrom, `${prefix}status` statTo, `${prefix}profile` prof
WHERE (statFrom.forAgileScrum=1 or statFrom.id=(select min(id) from `${prefix}tempupdate`)) and (statTo.forAgileScrum=1 or statTo.id=(select min(id) from `${prefix}tempupdate`)) and prof.idle=0;

DELETE FROM `${prefix}tempupdate` WHERE 1=1;

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `code`, `idWorkflow`, `defaultDuration`) VALUES 
('UserStory', 'Agile', '10', 'AGL', (SELECT `id` from `${prefix}workflow` where `name` = 'Agile'), null),
('Sprint', 'Agile', '10', 'AGL', (SELECT `id` from `${prefix}workflow` where `name` = 'Agile'), '10'),
('Epic', 'Agile', '10', 'AGL', (SELECT `id` from `${prefix}workflow` where `name` = 'Agile'), null);

INSERT INTO `${prefix}personas` (`name`, `code`, `sortOrder`, `idle`) VALUES
('User', 'USR', '10', '0'),
('Power User', 'USR+', '20', '0'),
('Business Manager', 'BIZ', '30', '0'),
('Administrator', 'ADM', '40', '0');

INSERT INTO `${prefix}scrumpriority` (`name`, `sortOrder`, `color`, `idle`) VALUES
('Must', '10', '#000000', '0'),
('Should', '20', '#ff0000', '0'),
('Could', '30', '#ffd700', '0'),
('Won''t', '40', '#32cd32', '0');

INSERT INTO `${prefix}copyable` (`name`, `idle`, `sortOrder`, `idDefaultCopyable`) VALUES
('Sprint', '0', '945', NULL);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES 
('UserStory', '0'),
('Sprint', '0'),
('Epic', '0');

-- Monthly Colored Planning : parameter full year
INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `idle`, `defaultValue`, `multiple`, `required`) VALUES
(4, 'includeNextElevenMonths','boolean','55','0',NULL, '0','0'),
(144, 'includeNextElevenMonths','boolean','55','0',NULL, '0','0');

-- Project Dashbord
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(326, 'menuProjectDashboard', 2, 'item', 105, 'Project', 0, 'Work Risk RequirementTest Financial Meeting');        

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 326, 1),
(2, 326, 1),
(3, 326, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 326, 8),
(2, 326, 8),
(3, 326, 7);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(427,'menuProjectDashboard',0,326,15,0),
(428,'menuProjectDashboard',1,326,15,0);

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(256, 0, 326, 0, 1);

-- Proportional Work 
ALTER TABLE `${prefix}assignment` ADD `proportional` INT(1) UNSIGNED NOT NULL DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}planningmode` ADD `proportional` INT(1) UNSIGNED NOT NULL DEFAULT '0' COMMENT '1';

CREATE TABLE `${prefix}passwordresetrequest` (
  `id`              int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idUser`          int(12) unsigned NOT NULL COMMENT '12',
  `email`           varchar(200) NOT NULL,
  `requestDateTime` datetime NOT NULL,
  `token`           varchar(1000) NOT NULL,
  `used`            int(1) NOT NULL DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

INSERT INTO `${prefix}parameter` (`idUser`, `parameterCode`, `parameterValue`)
VALUES (null, 'passwordResetEnabled', 'NO');

UPDATE `${prefix}menu` set sortOrder=sortOrder*5 where sortOrder<9000;
UPDATE `${prefix}menu` set sortOrder=180, idMenu=0 where id=133;
UPDATE `${prefix}menu` set sortOrder=630 where id=123;
UPDATE `${prefix}menu` set sortOrder=635 where id=313;
UPDATE `${prefix}menu` set sortOrder=1022 where id=232;
UPDATE `${prefix}menu` set sortOrder=4447 where id=200;
UPDATE `${prefix}menu` set sortOrder=4457 where id=171;
UPDATE `${prefix}menu` set sortOrder=680 where id=320;
UPDATE `${prefix}menu` set sortOrder=55, idMenu=0 where id=326;
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(327, 'menuAgile', 0, 'menu', 640, null, 1, 'Agile');
UPDATE `${prefix}menu` set idMenu=327 where id in (317,318,319,320,321,325);
UPDATE `${prefix}menu` set sortOrder=5280 where id=322;
UPDATE `${prefix}menu` set sortOrder=5282 where id=323;
UPDATE `${prefix}menu` set sortOrder=5284 where id=324;
UPDATE `${prefix}menu` set sortOrder=sortOrder+965 where id in (317,318,319,320,321,325,327,328);
