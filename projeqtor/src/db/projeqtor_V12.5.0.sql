-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.5.0                                      //
-- // Date : 2025-01-20                                     //
-- ///////////////////////////////////////////////////////////

-- Project Dashbord Detail
INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(329, 'menuProjectDashboardDetail', 0, 'item', 60, 'Project', 0, 'Work Risk RequirementTest Financial Meeting');        

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 329, 1),
(2, 329, 1),
(3, 329, 1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 329, 8),
(2, 329, 8),
(3, 329, 7);


INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(258, 0, 329, 0, 1);


-- Abacus
CREATE TABLE `${prefix}phasing` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

CREATE TABLE `${prefix}abacusdefinition` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(100) DEFAULT NULL,
  `className1` varchar(100) DEFAULT NULL,
  `className2` varchar(100) DEFAULT NULL,
  `className3` varchar(100) DEFAULT NULL,
  `className4` varchar(100) DEFAULT NULL,
  `className5` varchar(100) DEFAULT NULL,
  `idPhasing` int(12) DEFAULT NULL COMMENT '12',
  `abacusunit` varchar(1) DEFAULT 'd',
  `sortOrder` int(5) DEFAULT NULL COMMENT '5',
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_phasing` ON `${prefix}abacusdefinition` (`idPhasing`);

CREATE TABLE `${prefix}abacusline` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idAbacusDefinition` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idClassName1` int(12) DEFAULT NULL COMMENT '12',
  `idClassName2` int(12) DEFAULT NULL COMMENT '12',
  `idClassName3` int(12) DEFAULT NULL COMMENT '12',
  `idClassName4` int(12) DEFAULT NULL COMMENT '12',
  `idClassName5` int(12) DEFAULT NULL COMMENT '12',
  `assumption` varchar(4000) DEFAULT NULL,
  `example` varchar(4000) DEFAULT NULL,
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_abacusdef` ON `${prefix}abacusline` (`idAbacusDefinition`);

CREATE TABLE `${prefix}abacusable` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `className` varchar(100) DEFAULT NULL,
  `valueField` int(1) DEFAULT 0 COMMENT '1',
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;

INSERT INTO `${prefix}abacusable` (`className`,`valueField`) VALUES
('ResourceOrTeam',0),
('ResourceTeam',0),
('Resource',1);

CREATE TABLE `${prefix}abacusproject` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idProject` int(12) unsigned DEFAULT NULL COMMENT '12',
  `idAbacusDefinition` int(12) NOT NULL COMMENT '12',
  `idAffectable` int(12) DEFAULT NULL COMMENT '12',
  `idClassName1` int(12) DEFAULT NULL COMMENT '12',
  `idClassName2` int(12) DEFAULT NULL COMMENT '12',
  `idClassName3` int(12) DEFAULT NULL COMMENT '12',
  `idClassName4` int(12) DEFAULT NULL COMMENT '12',
  `idClassName5` int(12) DEFAULT NULL COMMENT '12',
  `quantity` decimal(5,2) DEFAULT 1.00,
  `comment` varchar(4000) DEFAULT NULL,
  `assignmentReference` varchar(4000) DEFAULT NULL,
  `idClassNameRef` int(12) DEFAULT NULL COMMENT '12',
  `idle` int(1) DEFAULT 0 COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci;
CREATE INDEX `idx_abacusproject_project` ON `${prefix}abacusproject` (`idProject`);
CREATE INDEX `idx_abacusproject_abacusdef` ON `${prefix}abacusproject` (`idAbacusDefinition`);

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES
(331,'menuAbacusDefinition', 6, 'item', 1896, 'Project', 0, 'Work Review'),
(332,'menuAbacusLine', 6, 'item', 1897, 'Project', 0, 'Work Review');

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`idReport`,`sortOrder`, `moduleName`) VALUES
(430, 'navAbacus',5,0,0,950,'moduleAbacus'),
(431, 'menuAbacusDefinition',430,331,0,20,'moduleAbacus'),
(432, 'menuAbacusLine',430,332,0,30,'moduleAbacus');

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1, 331, 1),
(2, 331, 1),
(3, 331, 1),
(1, 332, 1),
(2, 332, 1),
(3, 332, 1);


INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1, 332, 8),
(2, 332, 8),
(3, 332, 7),
(1, 331, 8),
(2, 331, 8),
(3, 331, 7);

INSERT INTO `${prefix}module` (`id`, `name`, `sortOrder`, `idModule`, `idle`, `active`, `parentActive`, `notActiveAlone`) VALUES
(38, 'moduleAbacus', 770, 10, '0', 0, '1', '0');

INSERT INTO `${prefix}modulemenu` (`id`,`idModule`,`idMenu`,`hidden`,`active`) VALUES
(259,38,331,0,0),
(260,38,332,0,0);

INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES 
('AbacusDefinition', '0'),
('AbacusLine', '0');

ALTER TABLE `${prefix}workelement` ADD COLUMN `idSprint` int(12) unsigned DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}linkable` (`name`,`idle`, `idDefaultLinkable`) VALUES 
('UserStory', 0, null),
('Epic', 0, null),
('Sprint', 0, null);

UPDATE `${prefix}navigation` set sortOrder=35 where name='navAgile';

ALTER TABLE `${prefix}client` ADD COLUMN `companyNumber` varchar(100) DEFAULT NULL;