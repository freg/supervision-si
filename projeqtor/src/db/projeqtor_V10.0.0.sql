-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.0.0                                       //
-- // Date : 2022-06-24                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}report` 
ADD COLUMN `referTo` varchar(100) DEFAULT NULL;

UPDATE `${prefix}report` set `referTo`='synthesisWork' WHERE id in (8,108,124,78);
UPDATE `${prefix}report` set `referTo`='planMonthly' WHERE id in (5,6,31,42,57,58);
UPDATE `${prefix}report` set `referTo`='planYearly' WHERE id in (60,121,122);
UPDATE `${prefix}report` set `referTo`='dispo' WHERE id in (32,52);
UPDATE `${prefix}report` set `referTo`='ticketSynthesisStatus' WHERE id in (119,120);
UPDATE `${prefix}report` set `referTo`='globalWorkPlanning' WHERE id in (76,77,128);
UPDATE `${prefix}report` set `referTo`='testCoverage' WHERE id in (41,43,44,53);
UPDATE `${prefix}report` set `referTo`='requirementFlow' WHERE id in (81,82,88);
UPDATE `${prefix}report` set `referTo`='ticketCount' WHERE id in (9,10,74,73);
UPDATE `${prefix}report` set `referTo`='ticketsRepartition' WHERE id in (14,15,16,18);


UPDATE `${prefix}reportparameter` set `defaultValue`='lastMonth' WHERE name='startDate' and idReport in (116);

CREATE TABLE `${prefix}skill` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`idSkill` int(12) unsigned DEFAULT NULL COMMENT '12',
`sbs` varchar(1000) DEFAULT NULL,
`sbsSortable` varchar(4000) DEFAULT NULL,
`description` mediumtext DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}skilllevel` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`sortOrder` int(3) unsigned DEFAULT NULL COMMENT '3',
`weight` decimal(14,5) DEFAULT NULL,
`icon` varchar(100) DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}resourceskill` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idResource` int(12) unsigned DEFAULT NULL COMMENT '12',
`idSkill` int(12) unsigned DEFAULT NULL COMMENT '12',
`idSkillLevel` int(12) unsigned DEFAULT NULL COMMENT '12',
`useSince` date DEFAULT NULL,
`useUntil` date DEFAULT NULL,
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
`comment` varchar(4000) DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}activityskill` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idActivity` int(12) unsigned DEFAULT NULL COMMENT '12',
`idSkill` int(12) unsigned DEFAULT NULL COMMENT '12',
`idSkillLevel` int(12) unsigned DEFAULT NULL COMMENT '12',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(275, 'menuSkill', 208, 'object', 441, null, 0, 'Skill',0),
(276, 'menuSkillLevel', 208, 'object', 442, null, 0, 'Skill',0),
(277, 'menuResourceSkill', 208, 'item', 443, null, 0, 'Skill',0),
(281, 'menuHierarchicalSkill', 208, 'item', 444, null, 0, 'Skill',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`) VALUES
(364, 'menuSkill',112,275,0,61),
(365, 'menuSkillLevel',112,276,0,63),
(366, 'menuResourceSkill',112,277,0,65),
(367, 'menuResource',112,44,0,67),
(373, 'menuHierarchicalSkill',112,281,0,62);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 275, 1),
(2, 275, 1),
(3, 275, 1),
(1, 276, 1),
(2, 276, 1),
(3, 276, 1),
(1, 277, 1),
(2, 277, 1),
(3, 277, 1),
(1, 281, 1),
(2, 281, 1),
(3, 281, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 275, 8),
(2, 275, 8),
(3, 275, 7),
(1, 276, 8),
(2, 276, 8),
(3, 276, 7),
(1, 277, 8),
(2, 277, 8),
(3, 277, 7),
(1, 281, 8),
(2, 281, 8),
(3, 281, 7);

UPDATE `${prefix}module` SET name='moduleAbsence',sortOrder='910',idModule=31,parentActive='1' WHERE name='moduleHumanResource';
UPDATE `${prefix}menu` SET isLeavesSystemMenu=0 WHERE name='mmenuHumanResource';

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`,`parentActive`,`notActiveAlone`) VALUES 
(31,'moduleHumanResource','900',null,0,(SELECT ms.active FROM  `${prefix}module` as ms WHERE ms.id=12 ),0,1),
(32,'moduleSkillManagement','920',31,0,0,1,0);

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(215,32,275,0,0),
(216,32,276,0,0),
(217,32,277,0,0),
(221,32,281,0,0),
(224,31,208,0,(SELECT ms.active FROM  `${prefix}module` as ms WHERE ms.id=31));

INSERT INTO `${prefix}skilllevel` (`name`,`sortOrder`,`weight`,`idle`, `icon`) VALUES 
('Trained','10',1,0,'skill_1-4.png'),
('Occasional use','20',2,0,'skill_2-4.png'),
('Regular use','30',3,0,'skill_3-4.png'),
('Expert','40',5,0,'skill_4-4.png');


ALTER TABLE `${prefix}type` ADD `mandatorySubTaskOnDone` int(1) unsigned DEFAULT '0' COMMENT '1';

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`, `multiple`, `required`) VALUES 
(7, 'displayAsGanttScreen', 'boolean', 50, 0,0,0),
(28, 'idRole', 'roleList', 8, 0,1,0),
(29, 'idRole', 'roleList', 8, 0,1,0),
(30, 'idRole', 'roleList', 8, 0,1,0),
(125, 'idRole', 'roleList', 22, 0,1,0);

ALTER TABLE `${prefix}status` ADD `setAssignedStatus` int(1) unsigned DEFAULT '0' COMMENT '1';

UPDATE `${prefix}status` set `setAssignedStatus`=1 WHERE name='assigné';

INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
('statusChangeAssignment', 'NO');

INSERT INTO `${prefix}importable` (`id`, `name`, `idle`) VALUES
(67, 'BillLine',0),
(68, 'Role',0);

-- GPA
-- VOTE ON TICKET
-- 

UPDATE `${prefix}menu` set `sortOrder`=162  WHERE name='menuRequirementTest';

CREATE TABLE `${prefix}votingattributionrule` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`refType` varchar(100) DEFAULT NULL,
`fixValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`dailyValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`weeklyValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`monthlyValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`yearlyValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}votingattribution` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`idVotingAttributionRule` int(12) unsigned DEFAULT NULL COMMENT '12',
`idClient` int(12) unsigned DEFAULT NULL COMMENT '12',
`totalValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`usedValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`leftValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`lastAttributionDate` date DEFAULT NULL,
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}votinguserule` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`name` varchar(100) DEFAULT NULL,
`idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`idType` int(12) unsigned DEFAULT NULL COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`idStatus` int(12) unsigned DEFAULT NULL COMMENT '12',
`workPointConvertion` decimal(5,2) unsigned DEFAULT NULL,
`fixValue` decimal(7,2) unsigned DEFAULT NULL,
`maxPointsPerUser` int(5) unsigned DEFAULT NULL COMMENT '5',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;


CREATE TABLE `${prefix}votingitem` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
`targetValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`actualValue` int(5) unsigned DEFAULT NULL COMMENT '5',
`pctRate` int(3) unsigned DEFAULT NULL COMMENT '3',
`locked` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;
CREATE UNIQUE INDEX votingItemId ON `${prefix}votingitem` (refType, refId);

CREATE TABLE `${prefix}voting` (
`id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
`refType` varchar(100) DEFAULT NULL,
`refId` int(12) unsigned DEFAULT NULL COMMENT '12',
`idUser` int(12) unsigned DEFAULT NULL COMMENT '12',
`idClient` int(12) unsigned DEFAULT NULL COMMENT '12',
`idVoter` int(12) unsigned DEFAULT NULL COMMENT '12',
`idNote` int(12) unsigned DEFAULT NULL COMMENT '12',
`value` int(5) unsigned DEFAULT NULL COMMENT '5',
`idle` int(1) unsigned DEFAULT '0' COMMENT '1',
PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`,`isLeavesSystemMenu`) VALUES
(278, 'menuVotingAttributionRule', 7, 'object', 155, null, 0, 'Admin',0),
(279, 'menuVotingUseRule', 7, 'object', 157, null, 0, 'Admin',0),
(280, 'menuVotingUseRulePerProject', 7, 'object', 158, null, 0, 'Admin',0),
(282, 'menuVotingFollowUp', 7, 'item', 159, null, 0, 'Admin',0),
(283, 'menuVotingAttributionFollowUp', 7, 'item', 160, null, 0, 'Admin',0);

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`,`moduleName`) VALUES
(368,'navVoting',3,0,0,140,'moduleVoting'),
(369, 'menuVotingAttributionRule',368,278,0,10,'moduleVoting'),
(370, 'menuVotingUseRule',368,279,0,20,'moduleVoting'),
(371, 'menuVotingUseRulePerProject',368,280,0,30,'moduleVoting'),
(372, 'navPoker',3,0,0,138,'moduleVoting'),
(374, 'menuVotingFollowUp',368,282,0,40,'moduleVoting'),
(375, 'menuVotingAttributionFollowUp',368,283,0,50,'moduleVoting'),
(376, 'menuUser',368,17,0,60,'moduleVoting'),
(377, 'menuClient',368,15,0,70,'moduleVoting');

UPDATE `${prefix}navigation` set `idParent`=372 WHERE `idMenu`=259;
UPDATE `${prefix}navigation` set `idParent`=372 WHERE `idMenu`=260;

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 278, 1),
(1, 279, 1),
(1, 280, 1),
(1, 282, 1),
(2, 282, 1),
(3, 282, 1),
(1, 283, 1),
(2, 283, 1),
(3, 283, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 278, 1000001),
(1, 279, 8),
(1, 280, 8),
(3, 280, 8),
(1,282,8),
(2,282,8),
(3,282,8),
(1, 283, 8),
(2, 283, 8),
(3, 283, 8);

INSERT INTO `${prefix}module` (`id`,`name`,`sortOrder`,`idModule`,`idle`,`active`,`parentActive`,`notActiveAlone`) VALUES 
(33,'moduleVoting','340',25,0,0,0,1);

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(218,33,278,0,0),
(219,33,279,0,0),
(220,33,280,0,0),
(222,33,282,0,0),
(223,33,283,0,0);

INSERT INTO `${prefix}habilitationother` (idProfile, rightAccess, scope) VALUES
(1,1,'canManageVotes'),
(3,1,'canManageVotes');

-- PBER : NEW INDEXES FOR PERFORMANCE
CREATE INDEX activityReference ON `${prefix}activity` (`reference`);
CREATE INDEX ticketReference ON `${prefix}ticket` (`reference`);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES
('Skill',0),
('ResourceSkill',0);
