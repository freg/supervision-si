-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.1.0                                      //
-- // Date : 2023-10-12                                     //
-- ///////////////////////////////////////////////////////////

-- Fix id for navigation
UPDATE `${prefix}navigation` SET id=100012001 WHERE name='menuImportProject';
UPDATE `${prefix}navigation` SET id=100019001 WHERE name='menuWebhook';
UPDATE `${prefix}navigation` SET id=378 WHERE name='menuCriticalResources' and id>378; 
UPDATE `${prefix}navigation` SET id=379 WHERE name='menuResourceMaterial' and id>379; 
UPDATE `${prefix}navigation` SET id=380 WHERE name='menuAssignment' and id>380; 
UPDATE `${prefix}navigation` SET id=381 WHERE name='menuActivityExpense' and id>381; 
UPDATE `${prefix}navigation` SET id=382 WHERE name='menuActivityExpenseType' and id>382; 

ALTER TABLE `${prefix}ticket` CHANGE `name` `name` varchar(200);
ALTER TABLE `${prefix}workelement` CHANGE `refName` `refName` varchar(200);

ALTER TABLE `${prefix}planningelement` 
ADD COLUMN `inheritedEndDate` date DEFAULT NULL;

ALTER TABLE `${prefix}planningelementbaseline` 
ADD COLUMN `inheritedEndDate` date DEFAULT NULL;

CREATE TABLE `${prefix}reportlayout` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',    
`idUser` int(12) unsigned NOT NULL COMMENT '12',
`scope` varchar(100) DEFAULT NULL,
`objectClass` varchar(50) DEFAULT NULL,
`sortOrder` int(3) unsigned DEFAULT '0' COMMENT '3',
`isShared` int(1) unsigned DEFAULT '0' COMMENT '1',
`idFilterCriteria` int(12) unsigned NULL COMMENT '12',
`directFilter` mediumtext DEFAULT NULL,
`comment` mediumtext DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE INDEX reportLayoutUser ON `${prefix}reportlayout` (`idUser`);
CREATE INDEX reportLayoutObjectClass ON `${prefix}reportlayout` (`objectClass`);

ALTER TABLE `${prefix}layoutcolumnselector` 
ADD COLUMN `isReportList` int(1) unsigned DEFAULT '0' COMMENT '1';

ALTER TABLE `${prefix}filtercriteria` 
ADD COLUMN `isReportList` int(1) unsigned DEFAULT '0' COMMENT '1';

INSERT INTO `${prefix}reportcategory` (`id`,`name`, `sortOrder`, `idle`) VALUES 
(21, 'reportCategoryObjectList', 100, 0);



-- ProjectAnalysis

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(389, 'navProjectAnalysis', 5, 0, 0, 900,'moduleProjectAnalysis'),
(390, 'menuAction', 389, 4, 0 ,500,'moduleProjectAnalysis');

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`,`parentActive`,`notActiveAlone`) VALUES 
(34,'moduleProjectAnalysis','760',10,0,0,0,0);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`,`idle`,`hasPrint`, `hasPdf`, `hasToday`, `hasWord`, `hasExcel`) VALUES
(142, 'reportProjectAnalysis', 10, 'reportProjectAnalysis.php', 1070,0, 1, 1, 1, 0, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(142, 'idProject', 'projectList', 10, 'currentProject');

INSERT INTO `${prefix}habilitationreport` (`idReport`, `idProfile`,  `allowAccess`) VALUES
(142, 1, 1),
(142, 2, 1),
(142, 3, 1);


-- Lessons Learned

CREATE TABLE `${prefix}lessonlearned` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`creationDateTime` datetime, 
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`idLessonLearnedType` int(12) unsigned NOT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idStatus` int(12) unsigned NOT NULL COMMENT '12',
`actionPlan` mediumtext DEFAULT NULL,
`result` mediumtext DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX lessonlearnproject ON `${prefix}lessonlearned` (`idProject`);

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(290, 'menuLessonLearned', 7, 'object', 142, 'Project', 0, 'Followup',0),
(291, 'menuLessonLearnedType', 79, 'object', 1050, 'ReadWriteType', 0, 'Followup',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(383, 'menuLessonLearned',389,290,0,300,'moduleProjectAnalysis'),
(384, 'menuLessonLearnedType',330,291,0,900,'moduleProjectAnalysis');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 290, 1),
(2, 290, 1),
(3, 290, 1),
(4, 290, 1),
(1, 291, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 290, 8),
(2, 290, 2),
(3, 290, 7),
(4, 290, 1),
(1, 291, 1000001);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('LessonLearned', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('LessonLearned', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('LessonLearned',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('LessonLearned', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('LessonLearned', '0');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('LessonLearned', 'resource', 10, 1, 0),
('LessonLearned', 'organizational', 20, 1, 0),
('LessonLearned', 'technical', 30, 1, 0),
('LessonLearned', 'financial', 40, 1, 0),
('LessonLearned', 'contractual', 50, 1, 0),
('LessonLearned', 'external', 60, 1, 0);



-- Assumption


CREATE TABLE `${prefix}assumption` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`creationDateTime` datetime, 
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`idAssumptionType` int(12) unsigned NOT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idStatus` int(12) unsigned NOT NULL COMMENT '12',
`idSeverity` int(12) unsigned NOT NULL COMMENT '12',
`idLikelihood` int(12) unsigned NOT NULL COMMENT '12',
`impact` mediumtext DEFAULT NULL,
`actionPlan` mediumtext DEFAULT NULL,
`result` mediumtext DEFAULT NULL,
`isFalseAssumption` int(1) unsigned NOT NULL COMMENT '1',
`isFalseDateAssumption` date,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX assumptionproject ON `${prefix}assumption` (`idProject`);

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(292, 'menuAssumption', 7, 'object', 145, 'Project', 0, 'Followup',0),
(293, 'menuAssumptionType', 79, 'object', 1051, 'ReadWriteType', 0, 'Followup',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(385, 'menuAssumption',389,292,0,100,'moduleProjectAnalysis'),
(386, 'menuAssumptionType',330,293,0,901,'moduleProjectAnalysis');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 292, 1),
(2, 292, 1),
(3, 292, 1),
(4, 292, 1),
(1, 293, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 292, 8),
(2, 292, 2),
(3, 292, 7),
(4, 292, 1),
(1, 293, 1000001);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('Assumption', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('Assumption', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('Assumption',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('Assumption', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('Assumption', '0');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('Assumption', 'resource', 10, 1, 0),
('Assumption', 'organizational', 20, 1, 0),
('Assumption', 'technical', 30, 1, 0),
('Assumption', 'financial', 40, 1, 0),
('Assumption', 'contractual', 50, 1, 0),
('Assumption', 'external', 60, 1, 0);



-- Constraint


CREATE TABLE `${prefix}constrainttable` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`creationDateTime` datetime, 
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`idConstraintType` int(12) unsigned NOT NULL COMMENT '12',
`description` mediumtext DEFAULT NULL,
`idStatus` int(12) unsigned NOT NULL COMMENT '12',
`idSeverity` int(12) unsigned NOT NULL COMMENT '12',
`idLikelihood` int(12) unsigned NOT NULL COMMENT '12',
`impact` mediumtext DEFAULT NULL,
`actionPlan` mediumtext DEFAULT NULL,
`result` mediumtext DEFAULT NULL,
`isFalseConstraint` int(1) unsigned NOT NULL COMMENT '1',
`isFalseDateConstraint` date,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE INDEX constraintproject ON `${prefix}constrainttable` (`idProject`);

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(294, 'menuConstraint', 7, 'object', 146, 'Project', 0, 'Followup',0),
(295, 'menuConstraintType', 79, 'object', 1052, 'ReadWriteType', 0, 'Followup',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(387, 'menuConstraint',389,294,0,200,'moduleProjectAnalysis'),
(388, 'menuConstraintType',330,295,0,902,'moduleProjectAnalysis');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 294, 1),
(2, 294, 1),
(3, 294, 1),
(4, 294, 1),
(1, 295, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 294, 8),
(2, 294, 2),
(3, 294, 7),
(4, 294, 1),
(1, 295, 1000001);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('Constraint', 0); 
INSERT INTO `${prefix}originable` (`name`, `idle`) VALUES ('Constraint', 0);
INSERT INTO `${prefix}linkable` (`name`,`idle`, idDefaultLinkable) VALUES ('Constraint',0,1);
INSERT INTO `${prefix}mailable` (name, idle) VALUES ('Constraint', 0);
INSERT INTO `${prefix}checklistable` (`name`, `idle`) VALUES ('Constraint', '0');

INSERT INTO `${prefix}type` (`scope`, `name`, `sortOrder`, `idWorkflow`, `idle`) VALUES 
('Constraint', 'resource', 10, 1, 0),
('Constraint', 'organizational', 20, 1, 0),
('Constraint', 'technical', 30, 1, 0),
('Constraint', 'financial', 40, 1, 0),
('Constraint', 'contractual', 50, 1, 0),
('Constraint', 'external', 60, 1, 0);

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(227,34,290,0,0),
(228,34,291,0,0),
(229,34,292,0,0),
(230,34,293,0,0),
(231,34,294,0,0),
(232,34,295,0,0);

ALTER TABLE `${prefix}inputmailbox` ADD COLUMN `addToFollowUp` int(1) unsigned DEFAULT '0' COMMENT '1';

-- Menu Risk Type
UPDATE `${prefix}navigation` SET sortOrder=15 where name='menuRiskType' and idParent=330;

-- New planningMode
INSERT INTO `${prefix}planningmode` (`id`, `applyTo`, `name`, `code`, `sortOrder`, `idle`, `mandatoryStartDate`, `mandatoryEndDate`) VALUES
(27, 'Activity', 'PlanningModeDDUR', 'DDUR', 400, 0 , 0, 0),
(28, 'TestSession', 'PlanningModeDDUR', 'DDUR', 400, 0 , 0, 0);

ALTER TABLE `${prefix}clientcontract`
ADD COLUMN `tokenOrdered` decimal(5,2) unsigned DEFAULT NULL,
ADD COLUMN `tokenUsed` decimal(5,2) unsigned DEFAULT NULL,
ADD COLUMN `tokenLeft` decimal(5,2) unsigned DEFAULT NULL;

INSERT INTO `${prefix}referencable` (`id`, `name`, `idle`) VALUES (30, 'ChangeRequest', 0);