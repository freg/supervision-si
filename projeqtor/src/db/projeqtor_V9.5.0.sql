-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.5.0                                       //
-- // Date : 2021-12-21                                     //
-- ///////////////////////////////////////////////////////////

CREATE TABLE `${prefix}worktoken` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`duration` decimal(8,5) unsigned DEFAULT NULL,
`amount` decimal(13,5) unsigned DEFAULT NULL,
`splittable` int(1) unsigned DEFAULT '0' COMMENT '1',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}worktokenmarkup` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idWorkToken` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`coefficient` decimal(6,3) unsigned DEFAULT NULL, 
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}worktokenclientcontract` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idWorkToken` int(12) unsigned DEFAULT NULL COMMENT '12',
`idClientContract` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`quantity` int(5)  unsigned DEFAULT NULL COMMENT '5',
`duration` decimal(13,5) unsigned DEFAULT NULL,
`amount` decimal(13,5) unsigned DEFAULT NULL,
`fullyConsumed` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}worktokenclientcontractwork` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idWork` int(12) unsigned DEFAULT NULL COMMENT '12',
`time` int(12) unsigned DEFAULT NULL COMMENT '12',
`idWorkTokenClientContract` int(12) unsigned DEFAULT NULL COMMENT '12',
`workTokenQuantity` decimal(5,2) unsigned DEFAULT NULL,
`idWorkTokenMarkup` int(12) unsigned DEFAULT NULL COMMENT '12',
`workTokenMarkupQuantity` decimal(5,2) unsigned DEFAULT NULL,
`billable` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;


INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(274, 'menuTokenDefinition', 152, 'object', 286, 'Project', 0, 'Financial');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`) VALUES
(362, 'menuTokenDefinition',14,274,0,95);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 274, 1),
(2, 274, 1),
(3, 274, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 274, 8),
(2, 274, 8),
(3, 274, 7);

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`) VALUES 
(30,'moduleTokenManagement','550',5,0,0); 

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(214,30,274,0,0);

INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
( 'afterMailTreatment', 'markAsReadMail'),
( 'refreshAuto', 0),
( 'refreshAutoTimer', 30);

INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'static','ResponsibleTodoList',null,7,0 FROM `${prefix}resource` as r 
WHERE r.isUser=1 and r.idle=0 and id not in (SELECT DISTINCT idUser FROM `${prefix}today` as t WHERE  t.staticSection='ResponsibleTodoList');


-- PBER
-- FIX TO SET DEFAULT AS READ FOR NON PROJET DEPENDANT ACCESS
-- 
INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 1, 1000001 from `${prefix}menu` M 
 where level like 'ReadWrite%'
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=1)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion');
 
INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 2, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%'
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=2)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 

INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 3, 1000001 from `${prefix}menu` M 
 where level like 'ReadWrite%' and M.id in (44,57,86,87,103,141,142,188,237)
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=3)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 
INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 3, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%' and M.id not in (44,57,86,87,103,141,142,188,237)
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=3)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 

INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 4, 1000001 from `${prefix}menu` M 
 where level like 'ReadWrite%' and M.id in (262,263)
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=4)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 
INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 4, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%' and M.id not in (262,263)
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=4)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion');  

INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 5, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%' 
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=5)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 

INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 6, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%' 
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=6)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion'); 
 
INSERT INTO `${prefix}accessright` (idMenu, idProfile, idAccessProfile)
SELECT id, 7, 1000002 from `${prefix}menu` M 
 where level like 'ReadWrite%'
 and not exists (select 'x' from `${prefix}accessright` X where X.idMenu=M.id and X.idProfile=7)
 and not exists (select 'x' from `${prefix}parameter` where parameterCode='dbVersion');    

UPDATE `${prefix}accessprofile` set sortOrder=100 where id=1000002;
UPDATE `${prefix}accessprofile` set sortOrder=200 where id=1000001;

ALTER TABLE `${prefix}statusmail` 
ADD COLUMN `alertToContact` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToUser` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToResource` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToProject` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToProjectIncludingParentProject` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToLeader` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToManager` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToAccountable` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToAssigned` int(1) unsigned DEFAULT 0 COMMENT '1',
ADD COLUMN `alertToSubscribers` int(1) unsigned DEFAULT 0 COMMENT '1';

-- Ticket / Activity synchronization
CREATE TABLE `${prefix}synchronization` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`originType` varchar(100) DEFAULT NULL,
`targetType` varchar(100) DEFAULT NULL,
`idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`idOrigineType` int(12) unsigned DEFAULT NULL COMMENT '12',
`idTargetType` int(12) unsigned DEFAULT NULL COMMENT '12',
`setActivity` int(1) unsigned DEFAULT 1 COMMENT '1', 
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}synchronizeditems` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idSynchronization` int(12) unsigned DEFAULT NULL COMMENT '12',
`ref1Type` varchar(100) DEFAULT NULL,
`ref1Id` int(12) unsigned DEFAULT NULL COMMENT '12',
`ref2Type` varchar(100) DEFAULT NULL,
`ref2Id` int(12) unsigned DEFAULT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX synchronizeditemsRef1 ON `${prefix}synchronizeditems` (`ref1Type`, `ref1Id`);
CREATE INDEX synchronizeditemsRef2 ON `${prefix}synchronizeditems` (`ref2Type`, `ref2Id`);
CREATE INDEX synchronizeditemsDefinition ON `${prefix}synchronizeditems` (`idSynchronization`);

ALTER TABLE `${prefix}reportparameter` 
ADD COLUMN `required` int(1)  unsigned DEFAULT '0' COMMENT '1';

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`) VALUES
(124, 'reportWorkPlanTwoDate',2, 'workPlan.php?scale=twoDate', 222,'1'),
(125, 'reportWorkDetailTwoDates',1, 'workDetail.php?scale=twoDate', 162,'1'),
(126, 'reportWorkUnitSynthesis',11, 'workUnitSynthesis.php', 1160,'1'),
(127, 'reportWorkPerActivityTwoDate',1, 'workPerActivity.php?scale=twoDate', 175,'1'),
(128, 'reportWorkPlanPerPeriods',2, 'workPlanPerPeriods.php', 278,'0');

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `multiple`, `required`) VALUES 
(124, 'idProject', 'projectList', 10, 'currentProject',0,0),
(124, 'startDate', 'date', 15,'lastMonth',0,1),
(124,'endDate','date',20,'today',0,1),
(124,'showIdle','boolean',25,null,0,0),
(125,'idProject', 'projectList', 5, 'currentProject',0,0),
(125,'idOrganization','organizationList',10,null,0,0),
(125,'idTeam','teamList',15,null,0,0),
(125,'idActivityType','activityTypeList',20,null,0,0),
(125,'startDate','date',25,'lastMonth',0,0),
(125,'endDate','date',30,'today',0,0),
(126,'idProject', 'projectList', 5, 'currentProject',0,1),
(126,'idActivityType','activityTypeList',10,null,0,0),
(126,'idProduct','productList',15,null,0,0),
(126,'idVersion','versionList',20,null,0,0),
(127, 'idProject', 'projectList', 10, 'currentProject',0,0),
(127, 'startDate', 'date', 15,'lastMonth',0,1),
(127,'endDate','date',20,'today',0,1),
(127,'showIdle','boolean',25,null,0,0),
(127, 'startDate', 'date', 15,'lastMonth',0,1),
(127,'endDate','date',20,'today',0,1),
(128, 'startDate', 'date', 10,'today',0,0),
(128,'endDate','date',15,'nextMonth',0,0),
(128,'idOrganization','organizationList',20,null,0,0),
(128,'idTeam','teamList',25,null,0,0),
(20,'idResource','resourceList',25,null,0,0),
(19,'idResource','resourceList',25,null,0,0),
(112,'idResource','resourceList',22,null,0,0),
(113,'idResource','resourceList',22,null,0,0),
(114,'idResource','resourceList',22,null,0,0),
(117,'idResource','resourceList',22,null,0,0);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 124, 1),
(1, 125, 1),
(1, 126, 1),
(1, 127, 1),
(1, 128, 1),
(2, 124, 1),
(2, 125, 1),
(2, 126, 1),
(2, 127, 1),
(2, 128, 1),
(3, 124, 1),
(3, 125, 1),
(3, 126, 1),
(3, 127, 1),
(3, 128, 1);

UPDATE `${prefix}report` SET hasExcel=1 where id in (8,28,29,30,40,123);

--FAR
-- MODIFICATION TO CONFIGURE THE MULTI PROJECT FOR A CATALOG
--

ALTER TABLE `${prefix}project` 
ADD COLUMN `idCatalogUO` int(12) unsigned DEFAULT NULL COMMENT '12';

ALTER TABLE `${prefix}workunit`
DROP `idProject`;

INSERT INTO `${prefix}importable` (`id`, `name`, `idle`) VALUES
(66, 'ProductVersionStructure',0);

--DSAN
-- MANAGE FAVORITES FOR PROJECT SELECTOR
-- 

CREATE TABLE `${prefix}favoriteprojectlist` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`sortOrder` int(3) unsigned DEFAULT NULL COMMENT '3',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}favoriteprojectitem` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idFavoriteProjectList` int(12) unsigned DEFAULT NULL COMMENT '12',
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

-- MAX DAILY WORK and MAX WEEKLY WORK ON RESOURCE
ALTER TABLE `${prefix}resource` ADD maxDailyWork NUMERIC(9,6) UNSIGNED DEFAULT NULL,
ADD maxWeeklyWork NUMERIC(9,6) UNSIGNED DEFAULT NULL;

ALTER TABLE `${prefix}planningelement` 
ADD COLUMN `automaticAssignment` int(1) unsigned DEFAULT '0' COMMENT '1';

ALTER TABLE `${prefix}planningelementbaseline` 
ADD COLUMN `automaticAssignment` int(1) unsigned DEFAULT '0' COMMENT '1';

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`) VALUES
(130, 'reportWorkTwoDatesResource',1, 'work.php', 192,'0'),
(131, 'reportWorkForAResourceByActivityTypeTwoDates',1, 'workPerTypeOfActivity.php', 198,'0');

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 130, 1),
(1, 131, 1),
(2, 130, 1),
(2, 131, 1),
(3, 130, 1),
(3, 131, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(130, 'idProject', 'projectList', 10, 'currentProject'),
(130, 'idResource', 'resourceList', 20, 'currentResource'),
(130, 'startDate','date',30,'lastMonth'),
(130, 'endDate','date',40,'today'),
(131, 'idProject', 'ProjectList', 10, NULL),
(131, 'idResource', 'resourceList', 20, NULL),
(131, 'idActivityType', 'activityTypeList', 30, NULL),
(131, 'showDetail', 'boolean', 40, NULL),
(131, 'startDate','date',50,'lastMonth'),
(131, 'endDate','date',60,'today');

INSERT INTO `${prefix}modulereport` (`id`,`idModule`,`idReport`,`hidden`,`active`) VALUES
(117,3,130,0,1),
(118,3,131,0,1);

UPDATE `${prefix}reportparameter` set `defaultValue`='lastMonth' WHERE name='startDate' and idReport=117;

ALTER TABLE `${prefix}workelement` ADD `tokenUsed` NUMERIC(5,2) DEFAULT NULL,
ADD `tokenBillable` NUMERIC(5,2) DEFAULT NULL;